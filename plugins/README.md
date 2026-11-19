# plugins/

这里是大肥鱼自己的插件源码。运行时它们在 `runtime/AstrBot-4.29.3/data/plugins/`，发版或本地调试时用脚本同步过去：

```powershell
python tools\sync_plugins.py          # 复制到运行目录
python tools\sync_plugins.py --check  # 只检查，不写文件
```

`dafeiyu_state.py` 不是插件，是插件共用的 JSON 状态读写模块；它会被复制到 `runtime/AstrBot-4.29.3/data/`，因为插件里写的是 `from data.dafeiyu_state import ...`。

改插件时的几个约定：

- 不要直接在 `runtime/.../data/plugins/` 里改，下次同步会被覆盖。改这里。
- `metadata.yaml` 里的 `author` 现在还是 `Local`，发布前可以换成自己的名字。
- `dafeiyu_diary/` 里的 `LICENSE` 是上游 cube-lover 的 MIT 许可，保留，别删；它对应的说明在 `NOTICE.md`。
- `astrbot_plugin_listen_music` 不在这里，因为它上游没有声明许可证。2.0.0 的完整包里有，2.0.1 起不随包；见 `NOTICE.md` 第 5 条。
