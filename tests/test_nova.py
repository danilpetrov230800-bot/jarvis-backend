import unittest

from nova.app import classify_command, parse_assistant_reply


class CommandSafetyTests(unittest.TestCase):
    def test_normal_command(self):
        risk, _ = classify_command("ls -la")
        self.assertEqual(risk, "normal")

    def test_elevated_command(self):
        risk, _ = classify_command("sudo apt install ffmpeg")
        self.assertEqual(risk, "elevated")

    def test_critical_command(self):
        risk, _ = classify_command("rm -rf /")
        self.assertEqual(risk, "critical")


class ReplyParsingTests(unittest.TestCase):
    def test_extracts_command(self):
        reply, command = parse_assistant_reply(
            "Проверю файлы.\n<nova_command>ls -la</nova_command>"
        )
        self.assertEqual(reply, "Проверю файлы.")
        self.assertEqual(command, "ls -la")

    def test_leaves_regular_reply_untouched(self):
        reply, command = parse_assistant_reply("Привет!")
        self.assertEqual(reply, "Привет!")
        self.assertIsNone(command)


if __name__ == "__main__":
    unittest.main()
