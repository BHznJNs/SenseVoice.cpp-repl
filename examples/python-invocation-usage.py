import re
from threading import Thread, Event
from typing import Generator, Literal
from queue import Queue, Empty as QueueEmptyException
from loguru import logger

def sensevoice_download_worker():
    from modelscope import model_file_download
    from modelscope.hub.errors import (
        NotExistError, 
        InvalidParameter, 
        FileDownloadError, 
        FileIntegrityError
    )
    try:
        model_path = model_file_download(
            model_id="lovemefan/SenseVoiceGGUF",
            file_path="sense-voice-small-fp16.gguf",
            local_dir="model",
        )
        assert model_path is not None
        result = {"status": "ok", "message": model_path}
    except NotExistError:
        logger.error("Model not found.")
        result = {"status": "error", "message": "E_INVALID_MODEL_NAME"}
    except FileDownloadError | FileIntegrityError:
        result = {"status": "error", "message": "E_NETWORK_ERROR"}
    except ValueError | InvalidParameter as e:
        logger.error(f"Invalid params: {e}")
        result = {"status": "error", "message": "E_UNEXPECTED_ERROR"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        result = {"status": "error", "message": "E_UNEXPECTED_ERROR"}
    return result


class SenseVoiceModel:
    def __init__(self,
        executable_path: str,
        model_path: str,
        language: Literal["auto", "zh", "en", "yue", "ja", "ko"]="auto",
    ):
        self._executable_path = executable_path
        self._model_path = model_path
        self._worker = Thread(target=self.communicate_worker, args=[language])
        self._worker.start()
        self._loaded = Event()
        self._input_queue: Queue[str] = Queue()
        self._output_queue: Queue[str | None] = Queue()
        self._loaded.wait()

    def shutdown(self):
        self._input_queue.put("exit")
        self._worker.join()

    def communicate_worker(self, language: str):
        import subprocess

        def resolve_output(process: subprocess.Popen) -> Generator[str, None, None]:
            sentinel_str = "[__DONE__]\n"
            assert process.stdout is not None
            while True:
                output = process.stdout.readline()
                if not output:
                    raise RuntimeError("SenseVoice stdout pipe closed unexpectedly.")
                if output == sentinel_str:
                    break
                yield output

        args = [
            self._executable_path,
            "-m", self._model_path,
            "-l", language,
            "-itn",
        ]
        process = subprocess.Popen(
            args=args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
        )

        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        # wait for init
        while process.stdout.readline() != "[__INIT__]\n": pass
        self._loaded.set()

        while True:
            if process.poll() is not None:
                logger.error("SenseVoice process has terminated unexpectedly.")
                break

            try:
                record_path = self._input_queue.get(timeout=0.1)
            except QueueEmptyException: continue

            try:
                process.stdin.write(record_path + "\n")
                process.stdin.flush()
                if record_path == "exit":
                    break
                for output in resolve_output(process):
                    self._output_queue.put(output.rstrip("\n"))
                self._output_queue.put(None)
            except (RuntimeError, IOError, BrokenPipeError) as e:
                logger.error(f"Error communicating with SenseVoice process: {e}")
                break

        try:
            returncode = process.wait(1)
        except subprocess.TimeoutExpired:
            process.terminate()
            returncode = process.returncode

        if returncode == 0: return
        # read all stderr output for debugging
        sensevoice_error = process.stderr.readlines()
        logger.warning(f"SenseVoice process exited with code {returncode}")
        logger.warning(f"Stderr: {sensevoice_error}")

    TIMES_DATA_PATTERN = re.compile(r'\[\d+\.\d+-\d+\.\d+\]\s')
    PREFIX_PATTERN = re.compile(r'<\|.*?\|>')

    @staticmethod
    def remove_metadata(transcription: str) -> str:
        # remove times data
        no_timestamps = SenseVoiceModel.TIMES_DATA_PATTERN.sub('', transcription)
        # remove prefix
        no_prefix = SenseVoiceModel.PREFIX_PATTERN.sub('', no_timestamps)
        return no_prefix

    def transcribe(self, record_path: str) -> Generator[str, None, None]:
        self._input_queue.put(record_path)
        while (output := self._output_queue.get()) is not None:
            yield SenseVoiceModel.remove_metadata(output)
