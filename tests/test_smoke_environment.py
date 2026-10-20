"""Exercise standalone smoke environment selection without a container daemon."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SmokeEnvironmentTests(unittest.TestCase):
    def test_environment_selection(self) -> None:
        """Defaults, overrides and missing files behave for both engines/modes."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'scripts').mkdir()
            library = root / 'deployment/lib/container/common.sh'
            library.parent.mkdir(parents=True)
            library.write_text((REPO_ROOT / 'lib/container/common.sh').read_text())
            script = root / 'scripts/smoke_test.sh'
            script.write_text(
                (REPO_ROOT / 'scaffold/templates/common/scripts/smoke_test.sh.tmpl')
                .read_text().replace('{{SMOKE_SERVICES_LITERAL}}', '(example)')
                .replace('{{SMOKE_PROFILE_CHECKS}}', '')
                .replace('{{APP_NAME}}', 'Example')
            )
            binaries = root / 'bin'
            binaries.mkdir()
            # Validate exported values and Compose arguments, including the
            # production --env-file injection. No real daemon or HTTP is used.
            mock = '''#!/bin/bash
[ "$EXAMPLE_INSTALL_PATH" = /opt/example ] || exit 21
[ "$EXAMPLE_APP_PORT" = 8765 ] || exit 22
if [ "$1" = compose ]; then shift; fi
if [ "$EXPECTED_MODE" = production ]; then
    [ "$1" = --env-file ] && [ "$2" = "$EXPECTED_ENV" ] || exit 23
    shift 2
fi
[ "$1" = -f ] && [ "$2" = "$EXPECTED_COMPOSE" ] && [ "$3" = config ] || exit 24
'''
            for name, content in [('docker', mock), ('podman', mock),
                                  ('podman-compose', mock),
                                  ('curl', '#!/bin/bash\nexit 0\n')]:
                executable = binaries / name
                executable.write_text(content)
                executable.chmod(0o755)
            for engine in ('docker', 'podman'):
                for mode in ('production', 'test'):
                    for custom in (False, True):
                        with self.subTest(engine=engine, mode=mode, custom=custom):
                            env_path = root / ('custom.env' if custom else f'.env.{mode}.file')
                            env_path.write_text("EXAMPLE_INSTALL_PATH='/opt/example'\nEXAMPLE_APP_PORT=8765\n")
                            compose_path = ('custom.yml' if custom else str(root / (
                                'docker-compose.test.yml' if mode == 'test' else 'docker-compose.prod.yml')))
                            environment = dict(os.environ, PATH=f'{binaries}:{os.environ["PATH"]}',
                                               EXPECTED_MODE=mode, EXPECTED_ENV=str(env_path),
                                               EXPECTED_COMPOSE=compose_path)
                            arguments = ['bash', str(script), '--engine', engine]
                            if mode == 'test':
                                arguments.append('--test')
                            if custom:
                                arguments.extend(['--env_file', str(env_path), '--compose_file', compose_path])
                            result = subprocess.run(arguments, cwd=temporary, env=environment,
                                                    capture_output=True, text=True)
                            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                            env_path.unlink()
                            result = subprocess.run(arguments, cwd=temporary, env=environment,
                                                    capture_output=True, text=True)
                            self.assertNotEqual(result.returncode, 0)
                            self.assertIn('Run container_install.sh first or supply --env_file PATH', result.stderr)


if __name__ == '__main__':
    unittest.main()
