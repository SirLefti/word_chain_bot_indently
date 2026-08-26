"""
Compares two sets of token score files, as produced by ``character_frequency.py``, side by side.

Both directories are expected to hold ``scores_<language code>.json`` files. The view shows one language and one game
mode at a time, tokens in alphabetical order, paged. Per token, the part both score sets have in common is drawn in a
neutral color, the difference on top of it in green if set B scores higher and in red if set A scores higher.

Run without arguments for an empty window and pick the directories interactively, or preselect any of the fields via
command line arguments.
"""

import argparse
import json
import logging
import statistics
import tkinter as tk
from math import ceil
from pathlib import Path
from tkinter import filedialog, ttk
from typing import NamedTuple

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from consts import GameMode
from language import DEFAULT_THRESHOLD_HARD, DEFAULT_THRESHOLD_NORMAL, Language

__LOGGER = logging.getLogger(__name__)

SCORE_FILE_PREFIX = 'scores_'
SCORE_FILE_PATTERN = f'{SCORE_FILE_PREFIX}*.json'

GAME_MODES: dict[str, GameMode] = {game_mode.name.lower(): game_mode for game_mode in GameMode}
"""Selectable game mode names mapped to their game mode. The enum value is the top level key in the score files."""

FALLBACK_THRESHOLDS: dict[GameMode, float] = {
    GameMode.NORMAL: DEFAULT_THRESHOLD_NORMAL,
    GameMode.HARD: DEFAULT_THRESHOLD_HARD
}
"""Only used for score files of languages the bot does not know, every known language brings its own thresholds."""

DEFAULT_PAGE_SIZE = 30

COLOR_COMMON = '#8b9198'
COLOR_B_HIGHER = '#2ca02c'
COLOR_A_HIGHER = '#d62728'
COLOR_THRESHOLD = '#1f77b4'
COLOR_FLIP = '#ff7f0e'


class TokenComparison(NamedTuple):
    """A single token with its score in both sets. Missing tokens count as zero."""
    token: str
    score_a: float
    score_b: float

    @property
    def common(self) -> float:
        return min(self.score_a, self.score_b)

    @property
    def difference(self) -> float:
        """Positive if set B scores higher, negative if set A scores higher."""
        return self.score_b - self.score_a

    def flips_at(self, threshold: float) -> bool:
        """Whether both sets end up on opposite sides of the threshold, which is the actual behavioral change."""
        return (self.score_a >= threshold) != (self.score_b >= threshold)


def in_game_threshold(language_code: str, game_mode: GameMode) -> float:
    """The threshold the bot applies in game, which the threshold input field starts from for every selection."""
    language = next((language for language in Language if language.value.code == language_code), None)
    if language is None:
        return FALLBACK_THRESHOLDS[game_mode]

    return language.value.score_threshold[game_mode]


def available_languages(directory: Path | None) -> set[str]:
    if directory is None or not directory.is_dir():
        return set()

    return {file.stem[len(SCORE_FILE_PREFIX):] for file in directory.glob(SCORE_FILE_PATTERN)}


def load_scores(directory: Path | None, language_code: str, game_mode: GameMode) -> dict[str, float]:
    """Reads the scores of one language and game mode. Returns an empty mapping if there is nothing to read."""
    if directory is None or not language_code:
        return {}

    file_path = directory / f'{SCORE_FILE_PREFIX}{language_code}.json'
    if not file_path.is_file():
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as score_file:
            content = json.load(score_file)
        return {str(token): float(score) for token, score in content[str(game_mode.value)].items()}
    except (KeyError, TypeError, ValueError) as error:
        __LOGGER.warning(f'could not read {file_path}: {error}')
        return {}


def compare_scores(scores_a: dict[str, float], scores_b: dict[str, float], hide_empty: bool) -> list[TokenComparison]:
    """Joins both score sets on their tokens, in alphabetical order. Both sets may use a different token set."""
    comparisons = [TokenComparison(token, scores_a.get(token, 0.0), scores_b.get(token, 0.0))
                   for token in sorted(set(scores_a) | set(scores_b))]

    if hide_empty:
        return [comparison for comparison in comparisons if comparison.score_a > 0 or comparison.score_b > 0]
    return comparisons


def summarize(comparisons: list[TokenComparison], threshold: float) -> str:
    if not comparisons:
        return 'no tokens to compare'

    scores_a = [comparison.score_a for comparison in comparisons]
    scores_b = [comparison.score_b for comparison in comparisons]
    b_higher = sum(1 for comparison in comparisons if comparison.difference > 0)
    a_higher = sum(1 for comparison in comparisons if comparison.difference < 0)
    total_difference = sum(abs(comparison.difference) for comparison in comparisons)
    passing_a = sum(1 for comparison in comparisons if comparison.score_a >= threshold)
    passing_b = sum(1 for comparison in comparisons if comparison.score_b >= threshold)
    flips = sum(1 for comparison in comparisons if comparison.flips_at(threshold))

    return (f'{len(comparisons)} tokens    '
            f'A: mean {statistics.mean(scores_a):.4f}, median {statistics.median(scores_a):.4f}    '
            f'B: mean {statistics.mean(scores_b):.4f}, median {statistics.median(scores_b):.4f}\n'
            f'B > A: {b_higher}    A > B: {a_higher}    equal: {len(comparisons) - a_higher - b_higher}    '
            f'sum of differences: {total_difference:.4f}    '
            f'at or above threshold: A {passing_a}, B {passing_b}, flipped {flips}')


class ComparisonApp(tk.Tk):

    def __init__(self, directory_a: Path | None, directory_b: Path | None, language_code: str | None,
                 game_mode: GameMode, threshold: float | None, page_size: int, page: int, log_scale: bool,
                 hide_empty: bool):
        super().__init__()
        self.title('token score comparison')
        self.geometry('1400x800')

        self.thresholds: dict[tuple[str, GameMode], float] = {}
        """Thresholds edited in the input field, per language and game mode, starting from the in game ones."""
        self.selection: tuple[str, GameMode] = (language_code or '', game_mode)
        self.page = max(0, page)
        self.comparisons: list[TokenComparison] = []

        self.directory_a_var = tk.StringVar(value=str(directory_a) if directory_a else '')
        self.directory_b_var = tk.StringVar(value=str(directory_b) if directory_b else '')
        self.language_var = tk.StringVar(value=language_code or '')
        self.game_mode_var = tk.StringVar(value=game_mode.name.lower())
        self.threshold_var = tk.StringVar()
        self.page_size_var = tk.StringVar(value=str(page_size))
        self.log_scale_var = tk.BooleanVar(value=log_scale)
        self.hide_empty_var = tk.BooleanVar(value=hide_empty)
        self.page_var = tk.StringVar(value='page 0 / 0')
        self.summary_var = tk.StringVar(value='')
        self.status_var = tk.StringVar(value='')

        self.__build_controls()
        self.__build_plot()

        self.bind('<Prior>', lambda _: self.__change_page(-1))
        self.bind('<Next>', lambda _: self.__change_page(1))

        self.refresh_languages()
        if threshold is not None:
            self.thresholds[(self.language_var.get(), game_mode)] = threshold
        self.__adopt_selection()
        self.reload()

    def __build_controls(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(side=tk.TOP, fill=tk.X)

        directories = ttk.Frame(controls)
        directories.pack(side=tk.TOP, fill=tk.X)
        for column, (label, variable) in enumerate([('score set A', self.directory_a_var),
                                                    ('score set B', self.directory_b_var)]):
            frame = ttk.Frame(directories)
            frame.grid(row=0, column=column, sticky=tk.EW, padx=(0, 12))
            directories.columnconfigure(column, weight=1)
            ttk.Label(frame, text=label, width=11).pack(side=tk.LEFT)
            entry = ttk.Entry(frame, textvariable=variable)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entry.bind('<Return>', lambda _: self.__on_directory_changed())
            entry.bind('<FocusOut>', lambda _: self.__on_directory_changed())
            ttk.Button(frame, text='browse', width=8,
                       command=lambda v=variable: self.__browse(v)).pack(side=tk.LEFT, padx=(4, 0))

        selectors = ttk.Frame(controls)
        selectors.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))

        ttk.Label(selectors, text='language').pack(side=tk.LEFT)
        self.language_box = ttk.Combobox(selectors, textvariable=self.language_var, state='readonly', width=6)
        self.language_box.pack(side=tk.LEFT, padx=(4, 12))
        self.language_box.bind('<<ComboboxSelected>>', lambda _: self.__on_selection_changed())

        ttk.Label(selectors, text='mode').pack(side=tk.LEFT)
        game_mode_box = ttk.Combobox(selectors, textvariable=self.game_mode_var, state='readonly', width=8,
                                     values=list(GAME_MODES))
        game_mode_box.pack(side=tk.LEFT, padx=(4, 12))
        game_mode_box.bind('<<ComboboxSelected>>', lambda _: self.__on_selection_changed())

        ttk.Label(selectors, text='threshold').pack(side=tk.LEFT)
        threshold_entry = ttk.Entry(selectors, textvariable=self.threshold_var, width=10)
        threshold_entry.pack(side=tk.LEFT, padx=(4, 4))
        threshold_entry.bind('<Return>', lambda _: self.redraw())
        threshold_entry.bind('<FocusOut>', lambda _: self.redraw())
        ttk.Button(selectors, text='reset', width=6,
                   command=self.__reset_threshold).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(selectors, text='tokens per page').pack(side=tk.LEFT)
        page_size_box = ttk.Spinbox(selectors, textvariable=self.page_size_var, from_=5, to=200, increment=5, width=6,
                                    command=self.redraw)
        page_size_box.pack(side=tk.LEFT, padx=(4, 12))
        page_size_box.bind('<Return>', lambda _: self.redraw())

        ttk.Checkbutton(selectors, text='logarithmic scale', variable=self.log_scale_var,
                        command=self.redraw).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(selectors, text='hide tokens without score in both sets', variable=self.hide_empty_var,
                        command=self.reload).pack(side=tk.LEFT)

        paging = ttk.Frame(controls)
        paging.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))
        ttk.Button(paging, text='<', width=3, command=lambda: self.__change_page(-1)).pack(side=tk.LEFT)
        ttk.Label(paging, textvariable=self.page_var, width=16, anchor=tk.CENTER).pack(side=tk.LEFT)
        ttk.Button(paging, text='>', width=3, command=lambda: self.__change_page(1)).pack(side=tk.LEFT)
        ttk.Label(paging, textvariable=self.status_var, foreground='#a05000').pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(controls, textvariable=self.summary_var, justify=tk.LEFT,
                  font=('TkFixedFont', 10)).pack(side=tk.TOP, anchor=tk.W, pady=(8, 0))

    def __build_plot(self) -> None:
        self.figure = Figure(figsize=(14, 6), dpi=100, layout='constrained')
        self.axes = self.figure.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        NavigationToolbar2Tk(self.canvas, self).update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def __browse(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(title='select a directory with score files',
                                           initialdir=variable.get() or '.')
        if selected:
            variable.set(selected)
            self.__on_directory_changed()

    def __on_directory_changed(self) -> None:
        previous_language = self.language_var.get()
        self.refresh_languages()
        if self.language_var.get() != previous_language:
            self.__on_selection_changed()
        else:
            self.reload()

    def __on_selection_changed(self) -> None:
        """Language and game mode have their own threshold each, so the input field follows the selection."""
        self.threshold()  # keeps whatever was typed for the selection we are leaving
        self.__adopt_selection()
        self.page = 0
        self.reload()

    def __adopt_selection(self) -> None:
        self.selection = self.language_var.get(), self.game_mode()
        self.threshold_var.set(f'{self.thresholds.get(self.selection, in_game_threshold(*self.selection)):g}')

    def __reset_threshold(self) -> None:
        self.thresholds.pop(self.selection, None)
        self.threshold_var.set(f'{in_game_threshold(*self.selection):g}')
        self.redraw()

    def __change_page(self, offset: int) -> None:
        self.page = max(0, self.page + offset)
        self.redraw()

    def directory(self, variable: tk.StringVar) -> Path | None:
        value = variable.get().strip()
        return Path(value) if value else None

    def game_mode(self) -> GameMode:
        return GAME_MODES[self.game_mode_var.get()]

    def threshold(self) -> float:
        """Reads the threshold input field, falling back to the last valid value of the current selection."""
        try:
            value = float(self.threshold_var.get().replace(',', '.'))
        except ValueError:
            return self.thresholds.get(self.selection, in_game_threshold(*self.selection))

        self.thresholds[self.selection] = value
        return value

    def page_size(self) -> int:
        try:
            return max(1, int(self.page_size_var.get()))
        except ValueError:
            return DEFAULT_PAGE_SIZE

    def refresh_languages(self) -> None:
        """Offers every language found in either directory, so a language missing on one side stays visible."""
        languages = sorted(available_languages(self.directory(self.directory_a_var))
                           | available_languages(self.directory(self.directory_b_var)))
        self.language_box.configure(values=languages)
        if self.language_var.get() not in languages:
            self.language_var.set(languages[0] if languages else '')

    def reload(self) -> None:
        """Reads both score files from disk and redraws. Directory, language, mode and filter changes need this."""
        directory_a = self.directory(self.directory_a_var)
        directory_b = self.directory(self.directory_b_var)
        language_code = self.language_var.get()
        game_mode = self.game_mode()

        scores_a = load_scores(directory_a, language_code, game_mode)
        scores_b = load_scores(directory_b, language_code, game_mode)
        self.comparisons = compare_scores(scores_a, scores_b, self.hide_empty_var.get())

        missing = [name for name, scores, directory in [('A', scores_a, directory_a), ('B', scores_b, directory_b)]
                   if not scores and directory is not None]
        if not directory_a or not directory_b:
            self.status_var.set('select a directory for both score sets')
        elif missing:
            self.status_var.set(f'no {language_code} scores in set {" and ".join(missing)}')
        else:
            self.status_var.set('')

        self.redraw()

    def redraw(self) -> None:
        """Renders the current page. Threshold, page size, scale and paging changes need this, but no re-read."""
        threshold = self.threshold()
        page_size = self.page_size()
        total_pages = max(1, ceil(len(self.comparisons) / page_size))
        self.page = min(self.page, total_pages - 1)
        page = self.comparisons[self.page * page_size:(self.page + 1) * page_size]
        self.page_var.set(f'page {self.page + 1} / {total_pages}')
        self.summary_var.set(summarize(self.comparisons, threshold))

        self.axes.clear()
        if not page:
            self.axes.text(0.5, 0.5, 'nothing to compare', ha='center', va='center', color='#8b9198',
                           transform=self.axes.transAxes)
            self.axes.set_axis_off()
            self.canvas.draw_idle()
            return

        self.axes.set_axis_on()
        positions = range(len(page))
        common = [comparison.common for comparison in page]
        gain_b = [max(0.0, comparison.difference) for comparison in page]
        gain_a = [max(0.0, -comparison.difference) for comparison in page]

        for position, comparison in zip(positions, page):
            if comparison.flips_at(threshold):
                self.axes.axvspan(position - 0.5, position + 0.5, color=COLOR_FLIP, alpha=0.15, zorder=0)

        self.axes.bar(positions, common, color=COLOR_COMMON, zorder=2)
        self.axes.bar(positions, gain_b, bottom=common, color=COLOR_B_HIGHER, zorder=2)
        self.axes.bar(positions, gain_a, bottom=common, color=COLOR_A_HIGHER, zorder=2)
        self.axes.axhline(threshold, color=COLOR_THRESHOLD, linestyle='--', linewidth=1, zorder=3)

        if self.log_scale_var.get():
            self.axes.set_yscale('log')
            positive = [score for comparison in page for score in (comparison.score_a, comparison.score_b) if score > 0]
            self.axes.set_ylim(bottom=min([*positive, threshold]) / 2)

        self.axes.set_xticks(list(positions), [comparison.token for comparison in page], family='monospace')
        for label, comparison in zip(self.axes.get_xticklabels(), page):
            if comparison.flips_at(threshold):
                label.set_color(COLOR_FLIP)
                label.set_fontweight('bold')

        self.axes.set_xlim(-0.75, len(page) - 0.25)
        self.axes.set_ylabel('token score')
        self.axes.set_title(f'{self.language_var.get()} · {self.game_mode_var.get()} mode · '
                            f'page {self.page + 1} of {total_pages}')
        self.axes.grid(axis='y', alpha=0.3, zorder=0)
        self.axes.legend(handles=[Patch(color=COLOR_COMMON, label='common part'),
                                  Patch(color=COLOR_B_HIGHER, label='B higher'),
                                  Patch(color=COLOR_A_HIGHER, label='A higher'),
                                  Patch(color=COLOR_FLIP, alpha=0.15, label='crosses threshold'),
                                  Patch(color=COLOR_THRESHOLD, label=f'threshold {threshold:g}')],
                         loc='upper left', bbox_to_anchor=(1.01, 1), framealpha=0.9)
        self.canvas.draw_idle()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('-a', '--dir-a', type=Path, default=None, help='directory holding score set A')
    parser.add_argument('-b', '--dir-b', type=Path, default=None, help='directory holding score set B')
    parser.add_argument('-l', '--language', default=None, help='language code to preselect, e.g. en')
    parser.add_argument('-m', '--mode', choices=list(GAME_MODES), default=GameMode.NORMAL.name.lower(),
                        help='game mode to preselect')
    parser.add_argument('-t', '--threshold', type=float, default=None,
                        help='threshold to start with, defaults to the one the bot uses in game')
    parser.add_argument('-p', '--page-size', type=int, default=DEFAULT_PAGE_SIZE, help='tokens shown per page')
    parser.add_argument('--page', type=int, default=1, help='page to start on, one based')
    parser.add_argument('--log', action='store_true', help='start with a logarithmic score axis')
    parser.add_argument('--hide-empty', action='store_true', help='hide tokens scoring zero in both sets')
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    for name, directory in [('--dir-a', arguments.dir_a), ('--dir-b', arguments.dir_b)]:
        if directory is not None and not directory.is_dir():
            raise SystemExit(f'{name}: {directory} is not a directory')

    app = ComparisonApp(directory_a=arguments.dir_a, directory_b=arguments.dir_b, language_code=arguments.language,
                        game_mode=GAME_MODES[arguments.mode], threshold=arguments.threshold,
                        page_size=arguments.page_size, page=arguments.page - 1, log_scale=arguments.log,
                        hide_empty=arguments.hide_empty)
    app.mainloop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
