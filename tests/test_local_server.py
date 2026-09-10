import unittest
from unittest.mock import patch

import local_server


class LocalServerLauncherTests(unittest.TestCase):
    def test_launcher_delegates_to_module5_serve(self):
        with patch.object(
            local_server, "module5_server_main", return_value=0
        ) as delegate:
            result = local_server.main(["--no-browser", "--port", "9000"])

        self.assertEqual(result, 0)
        delegate.assert_called_once_with(
            ["--no-browser", "--port", "9000"],
            prog="python src/local_server.py",
        )


if __name__ == "__main__":
    unittest.main()
