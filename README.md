# SenseVoice.cpp REPL

这是 [SenseVoice.cpp](https://github.com/lovemefan/SenseVoice.cpp/) 这个项目的 REPL 版本，旨在让 SenseVoice.cpp 能够更方便地被其它程序调用。

要查看原 README 请[点此](./README-original.md)

## 调用示例

- [Python](./examples/python-invocation-usage.py)

## Windows 构建

你可以[在此](./releases)下载预构建的可执行文件
可以从这两个链接下载已经转换好的模型文件 [huggingface](https://huggingface.co/lovemefan/sense-voice-gguf) [modelscope](https://www.modelscope.cn/models/lovemefan/SenseVoiceGGUF)

```powershell
git submodule sync; git submodule update --init --recursive
mkdir build; cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . --config Release -j 8
```
