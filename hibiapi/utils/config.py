import json
import os
from pathlib import Path
from typing import Any, Dict, Generic, Optional, Type, TypeVar, overload

import confuse  # type:ignore
import dotenv
from hibiapi import __file__ as root_file
from pydantic.generics import GenericModel

CONFIG_DIR = Path(".") / "configs"
DEFAULT_DIR = Path(root_file).parent / "configs"
ENV_DIR = CONFIG_DIR / ".env"

_T = TypeVar("_T")


def _generate_default() -> int:
    generated = 0
    for file in os.listdir(DEFAULT_DIR):
        default_path = DEFAULT_DIR / file
        config_path = CONFIG_DIR / file
        if config_path.is_file():
            continue
        generated += config_path.write_text(
            default_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return generated


if ENV_DIR.is_file():
    assert dotenv.load_dotenv(dotenv_path=ENV_DIR, verbose=True), "Failed to load .env"
else:
    assert _generate_default() <= 0, "Please complete config file!"


class _TypeChecker(GenericModel, Generic[_T]):
    value: _T


class ConfigSubView(confuse.Subview):
    @overload
    def get(self) -> Any:
        ...

    @overload
    def get(self, template: Type[_T]) -> _T:
        ...

    def get(self, template: Optional[Type[_T]] = None) -> _T:
        return _TypeChecker[template or Any](value=super().get()).value  # type:ignore

    def as_str(self) -> str:
        return self.get(str)

    def as_number(self) -> int:
        return self.get(int)

    def as_bool(self) -> bool:
        return self.get(bool)

    def as_path(self) -> Path:
        return self.get(Path)

    def as_dict(self) -> Dict[str, Any]:
        return self.get(Dict[str, Any])

    def __getitem__(self, key: str) -> "ConfigSubView":
        return self.__class__(self, key)


class AppConfig(confuse.Configuration):
    def __init__(self, name: str):
        self._config_name = name
        self._config = CONFIG_DIR / (filename := name + ".yml")
        self._default = DEFAULT_DIR / filename
        super().__init__(name)
        self._add_env_source()

    def config_dir(self) -> str:
        CONFIG_DIR.mkdir(exist_ok=True, parents=True)
        return str(CONFIG_DIR)

    @staticmethod
    def _generate_default_name(path: Path) -> Path:
        filename, ext = path.name.rsplit(".", 1)
        return path.with_name(filename + ".default." + ext)

    def user_config_path(self) -> str:
        return str(self._config)

    def _add_env_source(self):
        config_name = self._config_name.lower() + "_"
        env_configs = {
            k[len(config_name) :].lower(): str(v)
            for k, v in os.environ.items()
            if k.lower().startswith(config_name)
        }
        source_tree: Dict[str, Any] = {}
        for key, value in env_configs.items():
            # Convert `AAA_BBB_CCC=DDD` to `{'aaa':{'bbb':{'ccc':'ddd'}}}`
            _tmp = source_tree
            *nodes, name = key.split("_")
            for node in nodes:
                _tmp = _tmp.setdefault(node, {})
            if value == "":
                continue
            try:
                _tmp[name] = json.loads(value)
            except json.JSONDecodeError:
                _tmp[name] = value
        self.sources.insert(0, confuse.ConfigSource.of(source_tree))

    def _add_default_source(self):
        self.add(confuse.YamlSource(self._default, default=True))

    def _add_user_source(self):
        self.add(confuse.YamlSource(self._config, optional=True))

    def __getitem__(self, key: str) -> ConfigSubView:
        return ConfigSubView(self, key)


class GeneralConfig(AppConfig):
    def __init__(self, name: str):
        super().__init__(name)


class APIConfig(GeneralConfig):
    pass


Config = GeneralConfig("general")
DATA_PATH = Config["data"]["path"].as_path().expanduser().absolute()
DEBUG, VERSION = Config["debug"].as_bool(), Config["version"].as_str()