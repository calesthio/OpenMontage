"""
Attention Visualization Helpers - Converted from 3b1b ManimGL to ManimCE

Original: videos/_2024/transformers/helpers.py
Contains utility functions and classes for attention visualization.
"""

from manim import *
import numpy as np
import warnings
import random
from typing import Optional, Tuple


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def softmax(logits, temperature=1.0):
    """Numerically stable softmax function."""
    logits = np.array(logits)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        logits = logits - np.max(logits)
        exps = np.exp(np.divide(logits, temperature, where=temperature != 0))

    if np.isinf(exps).any() or np.isnan(exps).any() or temperature == 0:
        result = np.zeros_like(logits)
        result[np.argmax(logits)] = 1
        return result
    return exps / np.sum(exps)


def value_to_color(
    value,
    low_positive_color=BLUE_E,
    high_positive_color=BLUE_B,
    low_negative_color=RED_E,
    high_negative_color=RED_B,
    min_value=0.0,
    max_value=10.0
):
    """Map a numeric value to a color based on sign and magnitude."""
    # Clamp alpha between 0 and 1
    alpha = max(0, min(1, abs(value - min_value) / (max_value - min_value))) if max_value != min_value else 0.5

    if value >= 0:
        return interpolate_color(low_positive_color, high_positive_color, alpha)
    else:
        return interpolate_color(low_negative_color, high_negative_color, alpha)


def get_paragraph(words, line_len=40, font_size=48):
    """Handle word wrapping for text display."""
    words = list(map(str.strip, words))
    word_lens = list(map(len, words))
    lines = []
    lh, rh = 0, 0
    while rh < len(words):
        rh += 1
        if sum(word_lens[lh:rh]) > line_len:
            rh -= 1
            lines.append(words[lh:rh])
            lh = rh
    lines.append(words[lh:])
    text = "\n".join([" ".join(line).strip() for line in lines])
    return Text(text, font_size=font_size)


def random_bright_color(hue_range=(0.0, 1.0)):
    """Generate a random bright color within a hue range."""
    import colorsys
    hue = random.uniform(*hue_range)
    rgb = colorsys.hsv_to_rgb(hue, 0.7, 0.9)
    return rgb_to_color(rgb)


# =============================================================================
# CUSTOM MOBJECT CLASSES
# =============================================================================

class NumericEmbedding(VGroup):
    """
    A vertical vector of decimal numbers representing an embedding.
    Displays values with color coding based on magnitude.
    """

    def __init__(
        self,
        values: Optional[np.ndarray] = None,
        length: int = 7,
        num_decimal_places: int = 1,
        value_range: Tuple[float, float] = (-9.9, 9.9),
        show_ellipsis: bool = True,
        ellipsis_row: int = -2,
        dark_color=GREY_C,
        light_color=WHITE,
        bracket_color=GREY_B,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.value_range = value_range
        self.dark_color = dark_color
        self.light_color = light_color

        if values is None:
            values = np.random.uniform(*value_range, size=length)

        self.values = values
        self.length = len(values)

        # Create decimal number entries
        self.elements = VGroup()
        for i, val in enumerate(values):
            if show_ellipsis and i == (ellipsis_row % len(values)):
                entry = MathTex(r"\vdots")
            else:
                entry = DecimalNumber(
                    val,
                    num_decimal_places=num_decimal_places,
                    include_sign=True,
                    font_size=36
                )
                # Color based on value
                alpha = abs(val) / max(abs(value_range[0]), abs(value_range[1]))
                entry.set_color(interpolate_color(dark_color, light_color, alpha))
            self.elements.add(entry)

        self.elements.arrange(DOWN, buff=0.15)

        # Add brackets
        self.left_bracket = MathTex(r"\left[")
        self.right_bracket = MathTex(r"\right]")

        self.left_bracket.stretch_to_fit_height(self.elements.get_height() * 1.1)
        self.right_bracket.stretch_to_fit_height(self.elements.get_height() * 1.1)

        self.left_bracket.next_to(self.elements, LEFT, buff=0.1)
        self.right_bracket.next_to(self.elements, RIGHT, buff=0.1)

        self.left_bracket.set_color(bracket_color)
        self.right_bracket.set_color(bracket_color)

        self.add(self.left_bracket, self.elements, self.right_bracket)

    def get_brackets(self):
        return VGroup(self.left_bracket, self.right_bracket)

    def get_entries(self):
        return self.elements


class WeightMatrix(VGroup):
    """
    A matrix of decimal numbers with color-coded entries.
    Used to represent weight matrices in neural networks.
    """

    def __init__(
        self,
        values: Optional[np.ndarray] = None,
        shape: Tuple[int, int] = (6, 8),
        value_range: Tuple[float, float] = (-9.9, 9.9),
        num_decimal_places: int = 1,
        show_ellipsis: bool = True,
        ellipsis_row: int = -2,
        ellipsis_col: int = -2,
        low_positive_color=BLUE_E,
        high_positive_color=BLUE_B,
        low_negative_color=RED_E,
        high_negative_color=RED_B,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.shape = shape
        self.value_range = value_range
        self.low_positive_color = low_positive_color
        self.high_positive_color = high_positive_color
        self.low_negative_color = low_negative_color
        self.high_negative_color = high_negative_color

        if values is None:
            values = np.random.uniform(*value_range, size=shape)

        self.values = values

        # Create matrix entries
        self.rows = VGroup()
        n_rows, n_cols = shape

        for i in range(n_rows):
            row = VGroup()
            for j in range(n_cols):
                if show_ellipsis and i == (ellipsis_row % n_rows):
                    entry = MathTex(r"\vdots")
                elif show_ellipsis and j == (ellipsis_col % n_cols):
                    entry = MathTex(r"\cdots")
                else:
                    val = values[i, j]
                    entry = DecimalNumber(
                        val,
                        num_decimal_places=num_decimal_places,
                        include_sign=True,
                        font_size=24
                    )
                    entry.set_color(value_to_color(
                        val,
                        low_positive_color,
                        high_positive_color,
                        low_negative_color,
                        high_negative_color,
                        0, max(abs(value_range[0]), abs(value_range[1]))
                    ))
                row.add(entry)
            row.arrange(RIGHT, buff=0.2)
            self.rows.add(row)

        self.rows.arrange(DOWN, buff=0.15)

        # Add brackets
        self.left_bracket = MathTex(r"\left[")
        self.right_bracket = MathTex(r"\right]")

        self.left_bracket.stretch_to_fit_height(self.rows.get_height() * 1.1)
        self.right_bracket.stretch_to_fit_height(self.rows.get_height() * 1.1)

        self.left_bracket.next_to(self.rows, LEFT, buff=0.1)
        self.right_bracket.next_to(self.rows, RIGHT, buff=0.1)

        self.add(self.left_bracket, self.rows, self.right_bracket)

    def get_entries(self):
        entries = VGroup()
        for row in self.rows:
            for entry in row:
                if isinstance(entry, DecimalNumber):
                    entries.add(entry)
        return entries

    def get_rows(self):
        return self.rows


class ContextAnimation(LaggedStart):
    """
    Animation showing context flow from source words to target word.
    Creates arcing lines that flash from sources to target.
    """

    def __init__(
        self,
        target,
        sources,
        direction=UP,
        time_width=2,
        min_stroke_width=1,
        max_stroke_width=5,
        strengths=None,
        run_time=3,
        path_arc=PI / 2,
        **kwargs,
    ):
        arcs = VGroup()
        if strengths is None:
            strengths = np.random.random(len(sources)) ** 2

        for source, strength in zip(sources, strengths):
            sign = direction[1] * (-1) ** int(source.get_x() < target.get_x())
            arc = Line(
                source.get_edge_center(direction),
                target.get_edge_center(direction),
                path_arc=sign * path_arc,
            )
            arc.set_stroke(
                color=random_bright_color(hue_range=(0.1, 0.3)),
                width=interpolate(min_stroke_width, max_stroke_width, strength)
            )
            arcs.add(arc)

        arcs.shuffle()
        lag_ratio = 0.5 / max(len(arcs), 1)

        super().__init__(
            *[
                ShowPassingFlash(arc, time_width=time_width)
                for arc in arcs
            ],
            lag_ratio=lag_ratio,
            run_time=run_time,
            **kwargs,
        )


class NeuralNetwork(VGroup):
    """
    Visual representation of a neural network with layers and connections.
    """

    def __init__(
        self,
        layer_sizes=[6, 12, 6],
        neuron_radius=0.1,
        v_buff=0.3,
        h_buff=1.5,
        max_stroke_width=2.0,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.max_stroke_width = max_stroke_width

        # Create layers
        self.layers = VGroup()
        for n in layer_sizes:
            layer = VGroup(*[
                Circle(radius=neuron_radius, color=WHITE, fill_opacity=random.random())
                for _ in range(n)
            ])
            layer.arrange(DOWN, buff=v_buff)
            self.layers.add(layer)

        self.layers.arrange(RIGHT, buff=h_buff)

        # Create connections
        self.lines = VGroup()
        for l1, l2 in zip(self.layers, self.layers[1:]):
            layer_lines = VGroup()
            for n1 in l1:
                for n2 in l2:
                    line = Line(
                        n1.get_center(),
                        n2.get_center(),
                        buff=neuron_radius
                    )
                    line.set_stroke(
                        color=value_to_color(random.uniform(-10, 10)),
                        width=max_stroke_width * random.random(),
                        opacity=random.random() ** 2
                    )
                    layer_lines.add(line)
            self.lines.add(layer_lines)

        self.add(self.lines, self.layers)


class AttentionPattern(VGroup):
    """
    Visual representation of attention weights between tokens.
    Shows which tokens attend to which with varying line widths.
    """

    def __init__(
        self,
        n_tokens=8,
        token_labels=None,
        attention_weights=None,
        **kwargs
    ):
        super().__init__(**kwargs)

        if token_labels is None:
            token_labels = [f"T{i}" for i in range(n_tokens)]

        if attention_weights is None:
            # Random attention pattern
            attention_weights = softmax(np.random.randn(n_tokens, n_tokens), temperature=0.5)

        # Create token representations
        self.tokens = VGroup()
        for label in token_labels:
            token = VGroup(
                Square(side_length=0.8, color=BLUE, fill_opacity=0.3),
                Text(label, font_size=24)
            )
            token[1].move_to(token[0])
            self.tokens.add(token)

        self.tokens.arrange(RIGHT, buff=0.5)

        # Create attention lines (simplified - just showing strongest connections)
        self.attention_lines = VGroup()
        for i in range(n_tokens):
            for j in range(n_tokens):
                if attention_weights[i, j] > 0.1:  # Threshold
                    line = Line(
                        self.tokens[i].get_bottom(),
                        self.tokens[j].get_bottom(),
                        path_arc=-0.5,
                    )
                    line.set_stroke(
                        color=YELLOW,
                        width=attention_weights[i, j] * 5,
                        opacity=attention_weights[i, j]
                    )
                    self.attention_lines.add(line)

        self.add(self.tokens, self.attention_lines)


# =============================================================================
# ANIMATION HELPERS
# =============================================================================

class RandomizeMatrixEntries(Animation):
    """Animation that smoothly randomizes matrix entries."""

    def __init__(self, matrix, **kwargs):
        self.matrix = matrix
        self.entries = matrix.get_entries()
        self.start_values = [
            entry.get_value() if hasattr(entry, 'get_value') else 0
            for entry in self.entries
        ]
        self.target_values = np.random.uniform(
            matrix.value_range[0],
            matrix.value_range[1],
            len(self.entries)
        )
        super().__init__(matrix, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        for index, entry in enumerate(self.entries):
            if hasattr(entry, 'set_value'):
                start = self.start_values[index]
                target = self.target_values[index]
                entry.set_value(interpolate(start, target, alpha))


def show_attention_flow(scene, source_mobs, target_mob, weights=None, run_time=2):
    """Helper to animate attention flow from multiple sources to a target."""
    if weights is None:
        weights = np.random.random(len(source_mobs))
        weights = weights / weights.sum()

    arrows = VGroup()
    for source, weight in zip(source_mobs, weights):
        arrow = CurvedArrow(
            source.get_top(),
            target_mob.get_top(),
            angle=-TAU/4
        )
        arrow.set_stroke(width=weight * 5, color=YELLOW)
        arrow.set_opacity(weight)
        arrows.add(arrow)

    scene.play(
        LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.2),
        run_time=run_time
    )
    return arrows
