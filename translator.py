"""OpenAI \ubc88\uc5ed \ud074\ub77c\uc774\uc5b8\ud2b8 - Structured Outputs + \uacac\uace0\ud55c id \ub9e4\ud551 + \uacc4\uc870\uc801 \ud3f4\ubc31."""
from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from prompts import build_system_prompt, build_user_payload
from srt_chunker import Block, Chunk, blocks_to_dicts


log = logging.getLogger(__name__)


class TranslationMappingError(Exception):
    """\ubc18\ud658\ub41c id \uc9d1\ud569\uc774 \uc694\uccad\uacfc \ub2e4\ub97c \ub54c \ubc1c\uc0dd."""


def _clean_translation(text: str) -> str:
    """GPT \uc751\ub2f5 \ud14d\uc2a4\ud2b8\ub97c SRT \uc548\uc804 \ud14d\uc2a4\ud2b8\ub85c \uc815\ub9ac.

    - \uc904\ubc14\uafc8/\uc5f0\uc18d \uacf5\ubc31 \uc81c\uac70 (SRT \ud50c\ub808\uc774\uc5b4\uac00 \uc54c\uc544\uc11c \uc904 \ub098\ub234)
    - \uc22b\uc790\ub9cc\uc778 \ud1a0\ud070/\ub77c\uc778 \uc81c\uac70 (GPT\uac00 \uac04\ud639 \ube14\ub85d \ubc88\ud638\ub97c \uc5d0\ucf54\ud558\ub294 \uc624\ub958 \ubc29\uc9c0)
    - SRT \ubcf8\ubb38 \ub3c4\uc911\uc5d0 \uc22b\uc790\ub9cc \uc788\ub294 \ub77c\uc778\uc740 \ud30c\uc11c\uac00 \uc0c8 \ube14\ub85d\uc73c\ub85c \uc624\ud574\ud568.
    """
    if not text:
        return ""
    # \uc904 \ub2e8\uc704\ub85c \uc790\ub974\uace0 \uc22b\uc790\ub9cc\uc778 \ub77c\uc778 \ucd94\ucd9c
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not ln.isdigit()]
    joined = " ".join(lines)
    # \uc5f0\uc18d \uacf5\ubc31 \uc815\ub9ac
    joined = re.sub(r"\s+", " ", joined).strip()
    # \ubcf8\ubb38 \ub0b4\ubd80\uc5d0 ' 94 ' \uac19\uc740 \uace0\ub9bd\ub41c \uc22b\uc790 \ud1a0\ud070\uc774 \uc788\uc73c\uba74 \uc81c\uac70
    # (\ubc88\uc5ed\ubb38\uc5d0 \uc22b\uc790\uac00 \uc815\uc0c1\uc73c\ub85c \ud3ec\ud568\ub420 \uc218 \uc788\uc73c\ubbc0\ub85c \ube14\ub85d \ubc88\ud638 \ubc94\uc704\ub9cc \ubcf4\uc218\uc801\uc73c\ub85c \uc81c\uac70 \uc548\ud568)
    return joined


JSON_SCHEMA = {
    "name": "srt_translation",
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["id", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass
class TranslatorConfig:
    model: str
    target_lang: str
    glossary_path: object | None = None
    temperature: float = 0.2


class Translator:
    def __init__(self, cfg: TranslatorConfig, client: OpenAI | None = None):
        self.cfg = cfg
        self.client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.system_prompt = build_system_prompt(cfg.target_lang, cfg.glossary_path)

    # ---------- \ub0b4\ubd80: \ub2e8\uc77c API \ud638\ucd9c (\uc77c\uc2dc \uc7a5\uc560\uc5d0\ub9cc \uc7ac\uc2dc\ub3c4) ----------
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _call_api(self, translate_blocks: list[Block], context_before: list[Block], context_after: list[Block]) -> dict[int, str]:
        user_content = build_user_payload(
            translate_blocks=blocks_to_dicts(translate_blocks),
            context_before=blocks_to_dicts(context_before),
            context_after=blocks_to_dicts(context_after),
            target_lang=self.cfg.target_lang,
        )
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            temperature=self.cfg.temperature,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_schema", "json_schema": JSON_SCHEMA},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        items = data.get("items", [])
        return {int(it["id"]): _clean_translation(it["text"]) for it in items if "id" in it and "text" in it}

    # ---------- \uacf5\uac1c: \uacac\uace0\ud55c \ucd9c\ub825 \ubcf4\uc7a5 ----------
    def translate_chunk(self, chunk: Chunk, max_retry_missing: int = 2) -> dict[int, str]:
        """\uccad\ud06c \ud558\ub098 \ubc88\uc5ed. id \ub204\ub77d\uc774 \uc788\uc73c\uba74 \ub204\ub77d\ubd84\ub9cc \uc7ac\uc694\uccad, \ucd5c\uc885\uc801\uc73c\ub85c\ub3c4 \uc548 \ub418\uba74 \uc6d0\ubcf8 \uc720\uc9c0."""
        expected_ids = [b.id for b in chunk.translate]
        id_to_block = {b.id: b for b in chunk.translate}

        # 1) \uccab \uc2dc\ub3c4: \uccad\ud06c \uc804\uccb4
        try:
            got = self._call_api(chunk.translate, chunk.context_before, chunk.context_after)
        except Exception as e:
            log.warning("API call failed for chunk: %s", e)
            got = {}

        missing = [i for i in expected_ids if i not in got]

        # 2) \ub204\ub77d\ub41c id\ub9cc \ub2e4\uc2dc \uc694\uccad (\uc791\uac8c \ucabc\uac1c\uc11c)
        attempt = 0
        while missing and attempt < max_retry_missing:
            attempt += 1
            log.info("Retrying missing ids %s (attempt %d)", missing, attempt)
            sub_blocks = [id_to_block[i] for i in missing]
            try:
                more = self._call_api(sub_blocks, chunk.context_before, chunk.context_after)
            except Exception as e:
                log.warning("Retry call failed: %s", e)
                more = {}
            got.update({i: t for i, t in more.items() if i in id_to_block})
            missing = [i for i in expected_ids if i not in got]

        # 3) \uac01\uac1c \ub2e8\uc704 \ucd5c\uc885 \uc2dc\ub3c4
        for i in list(missing):
            try:
                solo = self._call_api([id_to_block[i]], chunk.context_before, chunk.context_after)
                if i in solo:
                    got[i] = solo[i]
            except Exception as e:
                log.warning("Solo retry failed for id %d: %s", i, e)

        # 4) \uadf8\ub798\ub3c4 \ube60\uc9c4 \uac8c \uc788\uc73c\uba74 \uc6d0\ubcf8 \ud14d\uc2a4\ud2b8\ub85c \ud3f4\ubc31
        result: dict[int, str] = {}
        fallback_ids: list[int] = []
        for i in expected_ids:
            if i in got:
                result[i] = got[i]
            else:
                result[i] = id_to_block[i].text
                fallback_ids.append(i)
        if fallback_ids:
            log.warning("Fell back to original text for ids: %s", fallback_ids)
        return result

    def translate_all(self, chunks: Iterable[Chunk]) -> dict[int, str]:
        merged: dict[int, str] = {}
        for chunk in chunks:
            merged.update(self.translate_chunk(chunk))
        return merged

