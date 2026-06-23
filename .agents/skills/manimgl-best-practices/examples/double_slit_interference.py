"""
Double Slit Interference Visualization

Demonstrates the classic double-slit experiment, showing how waves from two
slits interfere to create an interference pattern on a screen.

Based on 3Blue1Brown's diffraction visualizations.

Run: manimgl double_slit_interference.py DoubleSlitExperiment -w
"""
from manimlib import *
import numpy as np


class DoubleSlitExperiment(Scene):
    """
    Visualizes the double-slit experiment with wave interference.
    Shows plane wave hitting two slits and producing interference.
    """

    def construct(self):
        frame = self.camera.frame

        # Create barrier with two slits
        barrier_color = GREY_D
        slit_separation = 2.0
        slit_width = 0.15

        # Create barrier pieces
        barrier_y = -2
        barrier_left = Rectangle(width=6, height=0.3, fill_color=barrier_color, fill_opacity=1)
        barrier_left.set_stroke(WHITE, 1)
        barrier_left.move_to([-(slit_separation/2 + 3 + slit_width), barrier_y, 0])

        barrier_middle = Rectangle(width=slit_separation - 2*slit_width, height=0.3,
                                   fill_color=barrier_color, fill_opacity=1)
        barrier_middle.set_stroke(WHITE, 1)
        barrier_middle.move_to([0, barrier_y, 0])

        barrier_right = Rectangle(width=6, height=0.3, fill_color=barrier_color, fill_opacity=1)
        barrier_right.set_stroke(WHITE, 1)
        barrier_right.move_to([slit_separation/2 + 3 + slit_width, barrier_y, 0])

        barrier = VGroup(barrier_left, barrier_middle, barrier_right)

        # Slit positions
        slit1_pos = np.array([-slit_separation/2, barrier_y, 0])
        slit2_pos = np.array([slit_separation/2, barrier_y, 0])

        # Mark the slits
        slit1_marker = Dot(slit1_pos, color=RED, radius=0.1)
        slit2_marker = Dot(slit2_pos, color=BLUE, radius=0.1)

        # Screen to observe pattern
        screen = Rectangle(width=0.2, height=6)
        screen.set_fill(GREY_E, opacity=0.8)
        screen.set_stroke(WHITE, 1)
        screen.move_to([0, 4, 0])

        # Wave parameters
        wave_number = 2.0
        frequency = 0.4

        # Create incoming plane wave (simplified as horizontal lines)
        def get_incoming_wave(time):
            waves = VGroup()
            for offset in np.arange(-10, 0, 0.5 / wave_number):
                y = barrier_y - 1 + (time * frequency / wave_number + offset) % 3
                if y < barrier_y - 0.2:
                    line = Line([-7, y, 0], [7, y, 0])
                    alpha = 1 - (barrier_y - y) / 3
                    line.set_stroke(TEAL, width=2, opacity=0.5 * alpha)
                    waves.add(line)
            return waves

        # Create outgoing waves from slits
        def get_outgoing_waves(time):
            rings = VGroup()
            colors = [RED_B, BLUE_B]
            positions = [slit1_pos, slit2_pos]

            for pos, color in zip(positions, colors):
                for phase_offset in np.arange(0, 12, 0.5 / wave_number):
                    radius = (time * frequency / wave_number + phase_offset)
                    if 0.1 < radius < 8:
                        # Only show upper semicircle
                        arc = Arc(
                            start_angle=0,
                            angle=PI,
                            radius=radius
                        )
                        arc.move_arc_center_to(pos)
                        amplitude = np.exp(-0.15 * radius)
                        arc.set_stroke(color, width=1.5 + 2 * amplitude, opacity=0.6 * amplitude)
                        rings.add(arc)
            return rings

        # Create intensity pattern on screen
        def get_intensity_pattern(time):
            dots = VGroup()
            screen_y = 4
            for x in np.linspace(-3, 3, 120):
                point = np.array([x, screen_y, 0])

                # Calculate path difference
                r1 = np.linalg.norm(point - slit1_pos)
                r2 = np.linalg.norm(point - slit2_pos)

                # Interference
                phase1 = TAU * (wave_number * r1 - frequency * time)
                phase2 = TAU * (wave_number * r2 - frequency * time)

                amp1 = np.cos(phase1) / np.sqrt(1 + 0.1 * r1)
                amp2 = np.cos(phase2) / np.sqrt(1 + 0.1 * r2)

                total_intensity = ((amp1 + amp2) / 2) ** 2

                # Create dot
                dot = Dot([x, screen_y - 0.1 + 0.2 * total_intensity, 0], radius=0.03)
                brightness = 0.2 + 0.8 * total_intensity
                dot.set_fill(interpolate_color(BLACK, WHITE, brightness), opacity=1)
                dots.add(dot)

            return dots

        time_tracker = ValueTracker(0)
        incoming = always_redraw(lambda: get_incoming_wave(time_tracker.get_value()))
        outgoing = always_redraw(lambda: get_outgoing_waves(time_tracker.get_value()))
        intensity = always_redraw(lambda: get_intensity_pattern(time_tracker.get_value()))

        # Title
        title = Text("Double Slit Interference", font_size=48)
        title.to_corner(UL)
        title.set_backstroke(BLACK, 5)

        # Labels
        incoming_label = Text("Incoming Wave", font_size=24)
        incoming_label.next_to(barrier, DOWN, buff=0.5)
        incoming_label.set_backstroke(BLACK, 3)

        screen_label = Text("Detection Screen", font_size=24)
        screen_label.next_to(screen, RIGHT)
        screen_label.set_backstroke(BLACK, 3)

        # Add elements
        self.add(title)
        self.add(barrier)
        self.add(slit1_marker, slit2_marker)
        self.add(screen)
        self.add(incoming)
        self.add(outgoing)
        self.add(intensity)
        self.add(incoming_label, screen_label)

        # Animate
        self.play(
            time_tracker.animate.set_value(30),
            run_time=15,
            rate_func=linear
        )
        self.wait()


class PathDifferenceExplanation(Scene):
    """
    Explains the path difference concept in interference.
    Shows how different path lengths lead to phase differences.
    """

    def construct(self):
        # Two source points
        source1 = Dot(2 * LEFT + 2 * DOWN, color=RED, radius=0.15)
        source2 = Dot(2 * RIGHT + 2 * DOWN, color=BLUE, radius=0.15)

        source1_label = Text("S1", font_size=24, color=RED).next_to(source1, DOWN)
        source2_label = Text("S2", font_size=24, color=BLUE).next_to(source2, DOWN)

        # Target point
        target = Dot(UP, color=YELLOW, radius=0.15)
        target_label = Text("P", font_size=24, color=YELLOW).next_to(target, UP)

        # Path lines
        path1 = Line(source1.get_center(), target.get_center(), color=RED)
        path2 = Line(source2.get_center(), target.get_center(), color=BLUE)

        # Distance labels
        d1 = path1.get_length()
        d2 = path2.get_length()

        d1_label = Tex("d_1", color=RED, font_size=36)
        d1_label.move_to(path1.get_center() + 0.5 * LEFT)
        d2_label = Tex("d_2", color=BLUE, font_size=36)
        d2_label.move_to(path2.get_center() + 0.5 * RIGHT)

        # Title
        title = Text("Path Difference and Interference", font_size=42)
        title.to_edge(UP)

        # Add elements
        self.add(title)
        self.play(
            FadeIn(source1), FadeIn(source2),
            Write(source1_label), Write(source2_label)
        )
        self.play(FadeIn(target), Write(target_label))
        self.play(
            ShowCreation(path1), ShowCreation(path2),
            Write(d1_label), Write(d2_label)
        )
        self.wait()

        # Path difference formula
        formula = Tex(
            R"\Delta d = d_2 - d_1",
            font_size=48
        )
        formula.to_edge(DOWN)
        formula.shift(UP)

        self.play(Write(formula))
        self.wait()

        # Show constructive case
        constructive_text = Text("Constructive: path diff = n * wavelength", font_size=32)
        constructive_text.next_to(formula, DOWN)
        constructive_text.set_color(GREEN)

        self.play(Write(constructive_text))
        self.wait(2)

        # Show destructive case
        destructive_text = Text("Destructive: path diff = (n + 1/2) * wavelength", font_size=32)
        destructive_text.next_to(constructive_text, DOWN)
        destructive_text.set_color(PINK)

        self.play(Write(destructive_text))
        self.wait(2)


class DiffractionGratingSimple(Scene):
    """
    Simplified diffraction grating visualization showing multiple slits.
    """

    def construct(self):
        frame = self.camera.frame

        # Parameters
        n_slits = 8
        slit_spacing = 0.8
        barrier_y = -2
        wave_number = 3.0
        frequency = 0.3

        # Create barrier with multiple slits
        barrier_pieces = VGroup()
        slit_positions = []

        total_width = n_slits * slit_spacing
        for i in range(n_slits + 1):
            x_pos = -total_width / 2 + i * slit_spacing - slit_spacing / 4
            piece = Rectangle(width=slit_spacing / 2, height=0.3)
            piece.set_fill(GREY_D, opacity=1)
            piece.set_stroke(WHITE, 1)
            piece.move_to([x_pos, barrier_y, 0])
            barrier_pieces.add(piece)

            # Track slit positions (between pieces)
            if i < n_slits:
                slit_x = -total_width / 2 + i * slit_spacing + slit_spacing / 4
                slit_positions.append(np.array([slit_x, barrier_y, 0]))

        # Slit markers
        slit_markers = VGroup(
            Dot(pos, color=YELLOW, radius=0.05)
            for pos in slit_positions
        )

        # Create outgoing waves from all slits
        def get_grating_waves(time):
            rings = VGroup()
            for pos in slit_positions:
                for phase_offset in np.arange(0, 8, 0.4 / wave_number):
                    radius = (time * frequency / wave_number + phase_offset)
                    if 0.1 < radius < 6:
                        arc = Arc(
                            start_angle=0,
                            angle=PI,
                            radius=radius
                        )
                        arc.move_arc_center_to(pos)
                        amplitude = np.exp(-0.2 * radius)
                        arc.set_stroke(BLUE, width=1 + amplitude, opacity=0.3 * amplitude)
                        rings.add(arc)
            return rings

        time_tracker = ValueTracker(0)
        waves = always_redraw(lambda: get_grating_waves(time_tracker.get_value()))

        # Title
        title = Text("Diffraction Grating", font_size=48)
        title.to_edge(UP)
        title.set_backstroke(BLACK, 5)

        # Spacing label
        spacing_arrow = DoubleArrow(
            slit_positions[0] + 0.5 * DOWN,
            slit_positions[1] + 0.5 * DOWN,
            buff=0
        )
        spacing_arrow.set_color(WHITE)
        d_label = Tex("d", font_size=36)
        d_label.next_to(spacing_arrow, DOWN, buff=0.1)

        self.add(title)
        self.add(barrier_pieces)
        self.add(slit_markers)
        self.add(waves)
        self.add(spacing_arrow, d_label)

        # Animate
        self.play(
            time_tracker.animate.set_value(25),
            run_time=15,
            rate_func=linear
        )
        self.wait()
