import logging

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, _NOTHING, DEFAULT = range(10)
# The background is set with 40 plus the number of the color, and the foreground with 30
# These are the sequences needed to get colored output
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLOR_PATTERN = "%s%s%%s%s" % (COLOR_SEQ, COLOR_SEQ, RESET_SEQ)
LEVEL_COLOR_MAPPING = {
    logging.DEBUG: (BLUE, DEFAULT),
    logging.INFO: (GREEN, DEFAULT),
    logging.WARNING: (YELLOW, DEFAULT),
    logging.ERROR: (RED, DEFAULT),
    logging.CRITICAL: (WHITE, RED),
}
FORMAT_STR = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def colorized_msg(msg, level):
    fg_color, bg_color = LEVEL_COLOR_MAPPING.get(level, (GREEN, DEFAULT))
    colorized_msg_str = COLOR_PATTERN % (30 + fg_color, 40 + bg_color, msg)
    return colorized_msg_str


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        level_colorized = colorized_msg(record.levelname, record.levelno)
        record.levelname = level_colorized
        return logging.Formatter.format(self, record)
