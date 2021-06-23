import logging
import os
import subprocess


class VideoEditor:
    """Handles video related operations, such as intro concatenation"""

    @staticmethod
    def concatenate(video_path: str, intro_path: str = "media/intro.mp4", delete_source: bool = False) -> str:
        """
        concatenating two videos (intro with the main video) if needed. Intro is to be placed in media folder.
        """
        logging.info(f"Concatenating video {video_path} with intro {intro_path}")

        for path in [video_path, intro_path]:
            if not os.path.exists(intro_path):
                logging.error(f"File {path} not found. Cannot concatenate.")
                return ""

        concat_string = "file '" + intro_path + "/media/intro.mp4'\nfile '" + video_path + "'"
        # it should look like:
        #   file './media/intro.mp4'
        #   file './media/vid.mp4'
        with open("output/vidlist.txt", "w") as f:
            f.write(concat_string)
            f.close()

        filename = "".join(video_path.split(".")[:-1])
        extension = video_path.split(".")[-1]
        concat_filename = f"{filename}_concatenated.{extension}"
        concat_command = f"ffmpeg -f concat -safe 0 -i output/vidlist.txt -c copy {concat_filename}"
        # line looks like: ffmpeg -f concat -safe 0 -i vidlist.txt -c copy output.mp4. More on ffmpeg.org

        concat_process = subprocess.Popen(
            "exec " + concat_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )  # subprocess to execute ffmpeg utility command in shell and obtain all the flows

        concat_process.stdout.readline()  # wait till the process finishes

        # remove source files in necessary
        if delete_source:
            VideoEditor._remove_files(video_path)

        return concat_filename  # return new filename

    @staticmethod
    def _remove_files(*files) -> None:

        logging.info(f"Removing files: {files}")
        for file in files:
            os.remove(file)
