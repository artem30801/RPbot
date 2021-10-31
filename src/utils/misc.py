import math
import os
from typing import Any, List, Optional

guild_ids = None


def abs_join(*paths):
    return os.path.abspath(os.path.join(*paths))


def _make_solid_line(
    column_widths: List[int],
    left_char: str,
    middle_char: str,
    right_char: str,
) -> str:
    return f"{left_char}{middle_char.join('─' * (width + 2) for width in column_widths)}{right_char}"


def _make_data_line(column_widths: List[int], line: List[Any], align: str) -> str:
    return f"│ {' │ '.join(f'{str(value): {align}{width}}' for width, value in zip(column_widths, line))} │"


def make_table(
    rows: List[List[Any]], labels: Optional[List[Any]] = None, centered: bool = False
) -> str:
    """
    :param rows: 2D list containing objects that have a single-line representation (via `str`).
    All rows must be of the same length.
    :param labels: List containing the column labels. If present, the length must equal to that of each row.
    :param centered: If the items should be aligned to the center, else they are left aligned.
    :return: A table representing the rows passed in.
    """
    align = "^" if centered else "<"
    columns = zip(*rows) if labels is None else zip(*rows, labels)
    column_widths = [max(len(str(value)) for value in column) for column in columns]
    lines = [_make_solid_line(column_widths, "╭", "┬", "╮")]
    if labels is not None:
        lines.append(_make_data_line(column_widths, labels, align))
        lines.append(_make_solid_line(column_widths, "├", "┼", "┤"))
    for row in rows:
        lines.append(_make_data_line(column_widths, row, align))
    lines.append(_make_solid_line(column_widths, "╰", "┴", "╯"))
    return "\n".join(lines)


def make_progress_bar(
    width,
    value,
    max_value,
    label="",
    unit="",
    style=" ▄█",
    checkpoints=None,
    checkpoint_style="⧫◊",  # ⧫▾╳ ⟇
):
    lines = [f"╭╴{label}╶{'─'*(width-len(label)-2)}╮"]
    lines.append(
        f"├╢{_make__bar(width-2, value, max_value, style, checkpoints, checkpoint_style)}╟┤"
    )
    values = f"{value}/{max_value} {unit} - {value / max_value:.1%}"
    lines.append(f"╰{'─'*(width-len(values)-2)}╴{values}╶╯")
    return "\n".join(lines)


def _make__bar(width, value, max_value, style, checkpoints, checkpoint_style):
    #  ◌○●
    #  ▏▎▍▌▋▊▉█
    #  ▄█
    checkpoints = checkpoints or []
    progress = value / max_value
    progress = min(1, max(0, progress))
    whole_width = math.floor(progress * width)
    part_char = style[math.floor((progress * width) % 1 * (len(style) - 1))]
    if (width - whole_width - 1) < 0:
        part_char = ""
    bar = list(
        f"{style[-1] * whole_width}{part_char}{style[0] * (width - whole_width - 1)}"
    )
    for point in checkpoints:
        point_progress = point / max_value
        position = math.floor(point_progress * width)
        bar[position] = (
            checkpoint_style[0] if progress >= point_progress else checkpoint_style[1]
        )

    return "".join(bar)


# print(make_progress_bar(50, 39, 124, checkpoints=[10, 40, 100]))
