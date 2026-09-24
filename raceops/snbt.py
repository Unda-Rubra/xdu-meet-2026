"""Strict SNBT subset used by the tournament storage protocol."""
from __future__ import annotations

import json
import math
import re

NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[bBsSlLfFdD]?\Z")
BARE = re.compile(r"[A-Za-z0-9_.+-]+\Z")


class IntArray(list):
    """Minecraft UUID representation, distinct from an ordinary list."""


def dumps(value):
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) is int:
        return str(value) + ("L" if not -(2**31) <= value < 2**31 else "")
    if type(value) is float and math.isfinite(value):
        return repr(value) + "d"
    if isinstance(value, IntArray):
        if any(type(n) is not int or not -(2**31) <= n < 2**31 for n in value):
            raise ValueError("Invalid int array")
        return "[I;" + ",".join(str(n) for n in value) + "]"
    if isinstance(value, list):
        return "[" + ",".join(dumps(v) for v in value) + "]"
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return "{" + ",".join(dumps(k) + ":" + dumps(v) for k, v in value.items()) + "}"
    raise ValueError(f"Unsupported SNBT value: {type(value).__name__}")


class Reader:
    def __init__(self, text):
        if len(text) > 16 * 1024 * 1024:
            raise ValueError("SNBT exceeds response bound")
        self.text = text
        self.pos = 0

    def peek(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
        return self.text[self.pos:self.pos + 1]

    def take(self, expected):
        if self.peek() != expected:
            raise ValueError(f"Expected {expected!r} at SNBT offset {self.pos}")
        self.pos += 1

    def string(self):
        quote = self.peek()
        self.pos += 1
        result = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(result)
            if char == "\\":
                if self.pos >= len(self.text):
                    break
                char = self.text[self.pos]
                self.pos += 1
                if char not in (quote, "\\"):
                    raise ValueError("Invalid SNBT string escape")
            result.append(char)
        raise ValueError("Unterminated SNBT string")

    def token(self):
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in " \t\n\r,:{}[];":
            self.pos += 1
        token = self.text[start:self.pos]
        if not token or not BARE.fullmatch(token):
            raise ValueError(f"Invalid SNBT token at {start}")
        return token

    def value(self, depth=0):
        if depth > 64:
            raise ValueError("SNBT nesting limit exceeded")
        char = self.peek()
        if char in ('"', "'"):
            return self.string()
        if char == "{":
            self.take("{")
            result = {}
            while self.peek() != "}":
                key = self.string() if self.peek() in ('"', "'") else self.token()
                if key in result:
                    raise ValueError("Duplicate SNBT compound key")
                self.take(":")
                result[key] = self.value(depth + 1)
                if self.peek() != ",":
                    break
                self.take(",")
            self.take("}")
            return result
        if char == "[":
            self.take("[")
            typed = None
            if self.peek() in ("I", "L", "B") and self.text[self.pos + 1:self.pos + 2] == ";":
                typed = self.text[self.pos]
                self.pos += 2
            result = IntArray() if typed == "I" else []
            while self.peek() != "]":
                element = self.value(depth + 1)
                if typed and type(element) is not int:
                    raise ValueError("Non-integer in typed SNBT array")
                result.append(element)
                if self.peek() != ",":
                    break
                self.take(",")
            self.take("]")
            return result
        token = self.token()
        if token in ("true", "false"):
            return int(token == "true")
        if NUMBER.fullmatch(token):
            suffix = token[-1].lower()
            number = token[:-1] if suffix in "bslfd" else token
            result = float(number) if suffix in "fd" or "." in number or "e" in number.lower() else int(number)
            if isinstance(result, float) and not math.isfinite(result):
                raise ValueError("Non-finite SNBT number")
            return result
        return token


def loads(text):
    reader = Reader(text)
    result = reader.value()
    if reader.peek():
        raise ValueError("Trailing or truncated SNBT response")
    return result


def response_value(text):
    marker = " has the following contents: "
    if marker not in text:
        marker = " has the following entity data: "
    if marker not in text:
        raise ValueError(f"Expected complete storage response, got: {text[:160]}")
    return loads(text.split(marker, 1)[1])
