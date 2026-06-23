"""
MLP/Feedforward Neurons Flow Visualization

Shows data flowing through neurons in an MLP/Feedforward layer.
Based on 3Blue1Brown's transformer visualizations.

Run: manimgl mlp_neurons_flow.py MLPNeuronsFlow -o
"""
from manimlib import *
import numpy as np
import random


def value_to_color(
    value,
    low_positive_color=BLUE_E,
    high_positive_color=BLUE_B,
    low_negative_color=RED_E,
    high_negative_color=RED_B,
    min_value=0.0,
    max_value=10.0
):
    """Map a value to a color based on its sign and magnitude."""
    alpha = np.clip(float((abs(value) - min_value) / (max_value - min_value)), 0, 1)
    if value >= 0:
        return interpolate_color(low_positive_color, high_positive_color, alpha)
    else:
        return interpolate_color(low_negative_color, high_negative_color, alpha)


class MLPNeuronsFlow(Scene):
    """
    Visualizes data flowing through MLP/Feedforward neurons.

    Shows the expansion and contraction of data through the hidden layer.
    """

    def construct(self):
        frame = self.camera.frame

        # Title
        title = Text("Feedforward Layer: Neurons in Action", font_size=48)
        title.to_edge(UP)

        self.play(Write(title))
        self.wait()

        # Create input layer (small)
        input_layer = self.create_layer(8, radius=0.15, color=BLUE)
        input_layer.to_edge(LEFT, buff=2)

        # Create hidden layer (large - 4x expansion)
        hidden_layer = self.create_layer(24, radius=0.12, color=GREEN)
        hidden_layer.center()

        # Create output layer (same as input)
        output_layer = self.create_layer(8, radius=0.15, color=BLUE)
        output_layer.to_edge(RIGHT, buff=2)

        # Labels
        input_label = Text("Input\n(d dims)", font_size=24)
        input_label.next_to(input_layer, DOWN)

        hidden_label = Text("Hidden\n(4d dims)", font_size=24)
        hidden_label.next_to(hidden_layer, DOWN)

        output_label = Text("Output\n(d dims)", font_size=24)
        output_label.next_to(output_layer, DOWN)

        # Show layers
        self.play(
            FadeIn(input_layer, shift=RIGHT),
            FadeIn(input_label),
        )
        self.wait()

        self.play(
            FadeIn(hidden_layer, scale=0.8),
            FadeIn(hidden_label),
        )
        self.wait()

        self.play(
            FadeIn(output_layer, shift=LEFT),
            FadeIn(output_label),
        )
        self.wait()

        # Create connections (sparse for visibility)
        connections_in = self.create_connections(input_layer, hidden_layer, density=0.15)
        connections_out = self.create_connections(hidden_layer, output_layer, density=0.15)

        self.play(
            Write(connections_in, stroke_width=1),
            run_time=2
        )
        self.play(
            Write(connections_out, stroke_width=1),
            run_time=2
        )
        self.wait()

        # Animate data flow
        self.play_data_flow(connections_in, connections_out)

        # Show "this happens per token" note
        note = Text("This happens independently for each token position", font_size=30)
        note.next_to(title, DOWN, buff=0.5)

        self.play(FadeIn(note, shift=DOWN))
        self.wait(2)

        # Cleanup
        self.play(FadeOut(VGroup(
            title, note,
            input_layer, hidden_layer, output_layer,
            input_label, hidden_label, output_label,
            connections_in, connections_out
        )))

    def create_layer(self, n_neurons, radius=0.15, color=BLUE):
        """Create a vertical layer of neurons."""
        neurons = VGroup()
        for _ in range(n_neurons):
            dot = Dot(radius=radius)
            dot.set_fill(color, opacity=random.uniform(0.5, 1.0))
            dot.set_stroke(WHITE, 1)
            neurons.add(dot)

        neurons.arrange(DOWN, buff=0.15)
        neurons.set_height(5)
        return neurons

    def create_connections(self, layer1, layer2, density=0.2):
        """Create sparse connections between two layers."""
        lines = VGroup()
        for n1 in layer1:
            for n2 in layer2:
                if random.random() < density:
                    line = Line(
                        n1.get_center(), n2.get_center(),
                        buff=n1.get_width() / 2
                    )
                    line.set_stroke(
                        color=value_to_color(random.uniform(-10, 10)),
                        width=2 * random.random(),
                        opacity=0.6
                    )
                    lines.add(line)
        return lines

    def play_data_flow(self, connections_in, connections_out):
        """Animate data flowing through the network."""
        for _ in range(2):
            self.play(
                LaggedStart(*(
                    VShowPassingFlash(line.copy().set_stroke(YELLOW, 3), time_width=0.5)
                    for line in connections_in
                ), lag_ratio=0.01),
                run_time=1.5
            )
            self.play(
                LaggedStart(*(
                    VShowPassingFlash(line.copy().set_stroke(YELLOW, 3), time_width=0.5)
                    for line in connections_out
                ), lag_ratio=0.01),
                run_time=1.5
            )


class NeuralNetworkBasic(Scene):
    """
    Simple neural network visualization with multiple layers.
    """

    def construct(self):
        # Create network
        layer_sizes = [6, 12, 6]
        layers = VGroup()

        for n in layer_sizes:
            layer = VGroup(*(
                Dot(radius=0.12).set_fill(WHITE, opacity=random.uniform(0.4, 1.0))
                for _ in range(n)
            ))
            layer.arrange(DOWN, buff=0.2)
            layers.add(layer)

        layers.arrange(RIGHT, buff=2.5)
        layers.center()

        # Create connections
        all_connections = VGroup()
        for l1, l2 in zip(layers[:-1], layers[1:]):
            connections = VGroup()
            for n1 in l1:
                for n2 in l2:
                    line = Line(n1.get_center(), n2.get_center(), buff=0.12)
                    line.set_stroke(
                        value_to_color(random.uniform(-10, 10)),
                        width=2 * random.random() ** 2,
                        opacity=0.5
                    )
                    connections.add(line)
            all_connections.add(connections)

        # Layer labels
        labels = VGroup(
            Text("Input", font_size=30),
            Text("Hidden", font_size=30),
            Text("Output", font_size=30),
        )
        for label, layer in zip(labels, layers):
            label.next_to(layer, DOWN, buff=0.5)

        # Title
        title = Text("Simple Neural Network", font_size=48)
        title.to_edge(UP)

        # Animate
        self.play(Write(title))
        self.play(LaggedStartMap(FadeIn, layers[0], shift=RIGHT, lag_ratio=0.1))
        self.play(FadeIn(labels[0]))

        for i, (connections, layer, label) in enumerate(zip(all_connections, layers[1:], labels[1:])):
            self.play(
                Write(connections, lag_ratio=0.01),
                run_time=1.5
            )
            self.play(
                LaggedStartMap(FadeIn, layer, shift=RIGHT, lag_ratio=0.1),
                FadeIn(label),
            )

        self.wait()

        # Animate forward pass
        for _ in range(2):
            for connections in all_connections:
                self.play(
                    LaggedStart(*(
                        VShowPassingFlash(
                            line.copy().set_stroke(YELLOW, 4),
                            time_width=0.8
                        )
                        for line in connections
                    ), lag_ratio=0.005),
                    run_time=1.5
                )

        self.wait()

        # Cleanup
        self.play(FadeOut(VGroup(title, layers, all_connections, labels)))


class MLPExpansion3D(Scene):
    """
    3D visualization of MLP expansion from d to 4d dimensions.
    """

    def construct(self):
        frame = self.camera.frame
        frame.set_euler_angles(phi=70 * DEGREES, theta=-30 * DEGREES)

        # Title
        title = Text("MLP: Dimension Expansion", font_size=48)
        title.to_edge(UP)
        title.fix_in_frame()

        self.play(Write(title))

        # Create 3D neuron clusters
        input_neurons = self.create_3d_cluster(8, spread=0.3, color=BLUE)
        input_neurons.shift(3 * LEFT)

        hidden_neurons = self.create_3d_cluster(32, spread=0.8, color=GREEN)

        output_neurons = self.create_3d_cluster(8, spread=0.3, color=BLUE)
        output_neurons.shift(3 * RIGHT)

        # Labels
        for neurons, text in [(input_neurons, "d"), (hidden_neurons, "4d"), (output_neurons, "d")]:
            label = Text(text, font_size=36)
            label.next_to(neurons, DOWN, buff=0.5)
            neurons.add(label)

        # Show progression
        self.play(FadeIn(input_neurons, scale=0.8))
        self.wait()

        self.play(
            frame.animate.set_euler_angles(phi=65 * DEGREES, theta=-45 * DEGREES),
            TransformFromCopy(input_neurons[:-1], hidden_neurons[:-1]),
            FadeIn(hidden_neurons[-1]),
            run_time=2
        )
        self.wait()

        self.play(
            frame.animate.set_euler_angles(phi=60 * DEGREES, theta=-60 * DEGREES),
            TransformFromCopy(hidden_neurons[:-1], output_neurons[:-1]),
            FadeIn(output_neurons[-1]),
            run_time=2
        )
        self.wait()

        # Rotate view
        self.play(
            frame.animate.increment_theta(90 * DEGREES),
            run_time=3
        )
        self.wait()

        # Cleanup
        self.play(FadeOut(VGroup(title, input_neurons, hidden_neurons, output_neurons)))

    def create_3d_cluster(self, n_points, spread=0.5, color=BLUE):
        """Create a 3D cluster of points/neurons."""
        points = np.random.randn(n_points, 3) * spread
        dots = VGroup()

        for point in points:
            dot = Dot3D(radius=0.08)
            dot.move_to(point)
            dot.set_color(color)
            dot.set_opacity(random.uniform(0.6, 1.0))
            dots.add(dot)

        return dots
