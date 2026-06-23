"""
Basic Neural Network visualization with animated connections and layers.
Demonstrates: Custom VGroup class, randomized styling, layer-based animation
"""
from manimlib import *
import random
import itertools as it


def value_to_color(
    value,
    low_positive_color=BLUE_E,
    high_positive_color=BLUE_B,
    low_negative_color=RED_E,
    high_negative_color=RED_B,
    min_value=0.0,
    max_value=10.0
):
    """Map a numeric value to a color gradient."""
    alpha = clip(float(inverse_interpolate(min_value, max_value, abs(value))), 0, 1)
    if value >= 0:
        colors = (low_positive_color, high_positive_color)
    else:
        colors = (low_negative_color, high_negative_color)
    return interpolate_color_by_hsl(*colors, alpha)


class NeuralNetwork(VGroup):
    """A simple neural network visualization with layers and connections."""

    def __init__(
        self,
        layer_sizes=[6, 12, 6],
        neuron_radius=0.1,
        v_buff_ratio=1.0,
        h_buff_ratio=7.0,
        max_stroke_width=2.0,
        stroke_decay=2.0,
    ):
        self.max_stroke_width = max_stroke_width
        self.stroke_decay = stroke_decay

        # Create neuron layers
        layers = VGroup(*(
            Dot(radius=neuron_radius).get_grid(n, 1, v_buff_ratio=v_buff_ratio)
            for n in layer_sizes
        ))
        layers.arrange(RIGHT, buff=h_buff_ratio * layers[0].get_width())

        # Create connections between layers
        lines = VGroup(*(
            VGroup(*(
                Line(
                    n1.get_center(),
                    n2.get_center(),
                    buff=n1.get_width() / 2,
                )
                for n1, n2 in it.product(l1, l2)
            ))
            for l1, l2 in zip(layers, layers[1:])
        ))

        super().__init__(layers, lines)
        self.layers = layers
        self.lines = lines

        self.randomize_layer_values()
        self.randomize_line_style()

    def randomize_layer_values(self):
        """Randomize the fill opacity of neurons."""
        for layer in self.layers:
            for dot in layer:
                dot.set_stroke(WHITE, 1)
                dot.set_fill(WHITE, random.random())
        return self

    def randomize_line_style(self):
        """Randomize connection colors and widths."""
        for group in self.lines:
            for line in group:
                line.set_stroke(
                    value_to_color(random.uniform(-10, 10)),
                    self.max_stroke_width * random.random()**self.stroke_decay,
                )
        return self


class NeuralNetworkBasic(Scene):
    def construct(self):
        # Title
        title = Text("Neural Network", font_size=60)
        title.to_edge(UP)

        # Create neural network
        network = NeuralNetwork([5, 10, 5])
        network.set_height(5)
        network.center()

        self.play(FadeIn(title, shift=DOWN))
        self.wait(0.5)

        # Animate layers appearing
        self.play(
            FadeIn(network.layers[0]),
            ShowCreation(network.lines[0], lag_ratio=0.01),
            FadeIn(network.layers[1], lag_ratio=0.5),
            run_time=2
        )
        self.play(
            ShowCreation(network.lines[1], lag_ratio=0.01),
            FadeIn(network.layers[2], lag_ratio=0.5),
            run_time=2
        )

        # Ambiently change the network
        for _ in range(4):
            self.play(
                network.animate.randomize_line_style().randomize_layer_values(),
                run_time=2,
                lag_ratio=1e-4
            )

        # Add labels for layers
        input_label = Text("Input", font_size=36)
        hidden_label = Text("Hidden", font_size=36)
        output_label = Text("Output", font_size=36)

        input_label.next_to(network.layers[0], DOWN)
        hidden_label.next_to(network.layers[1], DOWN)
        output_label.next_to(network.layers[2], DOWN)

        self.play(LaggedStart(
            FadeIn(input_label, shift=UP),
            FadeIn(hidden_label, shift=UP),
            FadeIn(output_label, shift=UP),
            lag_ratio=0.3
        ))
        self.wait()

        # Final animation
        for _ in range(2):
            self.play(
                network.animate.randomize_line_style().randomize_layer_values(),
                run_time=2,
            )
        self.wait()
