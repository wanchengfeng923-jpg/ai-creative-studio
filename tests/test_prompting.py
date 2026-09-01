import unittest

from creative_studio.prompting import CompiledPrompt, compile_prompt


class CompiledPromptTests(unittest.TestCase):
    def test_renders_double_brace_placeholders_and_hashes_stably(self) -> None:
        first = CompiledPrompt("Hello, {{name}}!", {"name": "Ada", "tone": "warm"})
        second = compile_prompt("Hello, {{name}}!", {"tone": "warm", "name": "Ada"})

        self.assertEqual(first.render(), "Hello, Ada!")
        self.assertEqual(first.stable_hash(), second.stable_hash())
