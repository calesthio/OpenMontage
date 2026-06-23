"""
Simple ManimGL test without LaTeX

Run: PATH="/Library/TeX/texbin:$PATH" manimgl simple_test.py SimpleTest -w -l
"""
from manimlib import *


class SimpleTest(Scene):
    """Basic shapes test - no LaTeX required."""

    def construct(self):
        # Title using Text (no LaTeX needed)
        title = Text("ManimGL Test")
        title.to_edge(UP)
        self.play(Write(title))
        self.wait()

        # Create simple shapes
        circle = Circle(color=BLUE)
        circle.set_fill(BLUE, opacity=0.5)

        square = Square(color=RED)
        square.set_fill(RED, opacity=0.5)

        triangle = Triangle(color=GREEN)
        triangle.set_fill(GREEN, opacity=0.5)

        shapes = VGroup(circle, square, triangle)
        shapes.arrange(RIGHT, buff=1)

        self.play(
            LaggedStart(
                *[ShowCreation(s) for s in shapes],
                lag_ratio=0.3
            )
        )
        self.wait()

        # Transform
        self.play(
            circle.animate.shift(UP),
            square.animate.rotate(PI/4),
            triangle.animate.scale(1.5),
        )
        self.wait()

        # Fade out
        self.play(FadeOut(VGroup(shapes, title)))


class Simple3D(Scene):
    """Basic 3D test."""

    def construct(self):
        frame = self.camera.frame

        # 3D axes
        axes = ThreeDAxes()
        self.add(axes)

        # Sphere
        sphere = Sphere(radius=1)
        sphere.set_color(BLUE)
        self.add(sphere)

        # Rotate camera
        self.play(
            frame.animate.set_euler_angles(
                phi=70 * DEGREES,
                theta=-45 * DEGREES
            ),
            run_time=2
        )
        self.wait()

        # Rotate around
        self.play(
            frame.animate.increment_theta(90 * DEGREES),
            run_time=3
        )
        self.wait()
