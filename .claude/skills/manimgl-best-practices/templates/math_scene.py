"""
Mathematical Scene Template for ManimGL

Template for creating mathematical derivations and visualizations.

Usage:
    manimgl templates/math_scene.py MathSceneTemplate
    manimgl templates/math_scene.py MathSceneTemplate -l
"""

from manimlib import *


class MathSceneTemplate(Scene):
    """
    Template for mathematical derivations and equations.

    Key features:
    - Use Tex(R"...") for LaTeX (note capital R)
    - Use t2c for coloring parts of equations
    - Use TransformMatchingTex for equation transformations
    - Use isolate parameter for better control
    """

    def construct(self):
        # === TITLE ===
        title = Text("Mathematical Derivation", font_size=60)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait()

        # === INITIAL EQUATION ===
        # Use Tex with raw strings (capital R)
        eq1 = Tex(
            R"(a + b)^2",
            font_size=60
        )
        self.play(Write(eq1))
        self.wait()

        # === EXPANSION ===
        eq2 = Tex(
            R"(a + b)(a + b)",
            font_size=60
        )
        eq2.move_to(eq1)

        self.play(TransformMatchingTex(eq1, eq2))
        self.wait()

        # === FINAL FORM (with coloring) ===
        eq3 = Tex(
            R"a^2 + 2ab + b^2",
            font_size=60,
            t2c={"a": BLUE, "b": GREEN}  # Color variables
        )
        eq3.move_to(eq2)

        self.play(TransformMatchingTex(eq2, eq3))
        self.wait(2)

        # === CLEANUP ===
        self.play(FadeOut(VGroup(title, eq3)))


class QuadraticFormulaTemplate(Scene):
    """
    Template showing step-by-step derivation.
    """

    def construct(self):
        title = Text("Quadratic Formula Derivation", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait()

        # Steps of derivation
        steps = [
            Tex(R"ax^2 + bx + c = 0"),
            Tex(R"x^2 + \frac{b}{a}x + \frac{c}{a} = 0"),
            Tex(R"x^2 + \frac{b}{a}x = -\frac{c}{a}"),
            Tex(R"x^2 + \frac{b}{a}x + \frac{b^2}{4a^2} = \frac{b^2}{4a^2} - \frac{c}{a}"),
            Tex(R"\left(x + \frac{b}{2a}\right)^2 = \frac{b^2 - 4ac}{4a^2}"),
            Tex(R"x + \frac{b}{2a} = \pm\frac{\sqrt{b^2 - 4ac}}{2a}"),
            Tex(R"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"),
        ]

        # Position first equation
        current_eq = steps[0]
        current_eq.next_to(title, DOWN, buff=1)
        self.play(Write(current_eq))
        self.wait()

        # Transform through each step
        for next_eq in steps[1:]:
            next_eq.move_to(current_eq)
            self.play(TransformMatchingTex(current_eq.copy(), next_eq))
            current_eq = next_eq
            self.wait()

        self.wait(2)


class ColoredMathTemplate(Scene):
    """
    Template for color-coded mathematical expressions.
    """

    def construct(self):
        title = Text("Color-Coded Math", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Color-code different parts
        equation = Tex(
            R"\int_0^1 x^2 \, dx = \left[\frac{x^3}{3}\right]_0^1 = \frac{1}{3}",
            t2c={
                R"\int": BLUE,      # Integral sign
                "x": GREEN,          # Variable
                R"\frac": YELLOW,   # Fractions
                "1": RED,            # Constants
                "3": RED
            }
        )
        equation.next_to(title, DOWN, buff=1)

        self.play(Write(equation))
        self.wait(2)

        # Highlight specific part
        parts = equation.get_parts_by_tex(R"\frac{1}{3}")
        self.play(
            parts.animate.set_color(ORANGE).scale(1.3)
        )
        self.wait(2)


class AlignedEquationsTemplate(Scene):
    """
    Template for aligned equations.
    """

    def construct(self):
        title = Text("System of Equations", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Create multiple equations
        equations = VGroup(
            Tex(R"2x + 3y = 7"),
            Tex(R"x - y = 1"),
        )
        equations.arrange(DOWN, aligned_edge=LEFT, buff=0.5)
        equations.next_to(title, DOWN, buff=1)

        # Write equations
        for eq in equations:
            self.play(Write(eq))
            self.wait(0.5)

        self.wait()

        # Solution
        solution = VGroup(
            Tex(R"x = 2"),
            Tex(R"y = 1")
        )
        solution.arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        solution.next_to(equations, DOWN, buff=1)

        self.play(FadeIn(solution, shift=UP))
        self.wait(2)


class CalculusVisualizationTemplate(Scene):
    """
    Template combining equations with visual elements.
    """

    def construct(self):
        # === EQUATION ===
        integral = Tex(
            R"\int_a^b f(x) \, dx",
            font_size=60,
            t2c={"f(x)": BLUE, "a": RED, "b": RED}
        )
        integral.to_edge(UP)
        self.play(Write(integral))
        self.wait()

        # === VISUALIZATION ===
        # Create axes
        axes = Axes(
            x_range=[-1, 5],
            y_range=[-1, 5],
            width=10,
            height=6
        )
        axes.add_coordinate_labels(font_size=20)

        # Function
        graph = axes.get_graph(
            lambda x: 0.2 * (x - 2)**2 + 1,
            x_range=[1, 4],
            color=BLUE
        )

        # Riemann rectangles
        rects = axes.get_riemann_rectangles(
            graph,
            x_range=[1, 4],
            dx=0.5,
            color=BLUE,
            fill_opacity=0.5
        )

        # Show visualization
        self.play(
            ShowCreation(axes),
            ShowCreation(graph)
        )
        self.wait()

        self.play(ShowCreation(rects))
        self.wait(2)


class ComplexNumbersTemplate(Scene):
    """
    Template for complex number visualization.
    """

    def construct(self):
        title = Text("Complex Numbers", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Euler's formula
        euler = Tex(
            R"e^{i\theta} = \cos\theta + i\sin\theta",
            font_size=48,
            t2c={
                "e": BLUE,
                R"\theta": GREEN,
                R"\cos": YELLOW,
                R"\sin": YELLOW,
                "i": RED
            }
        )
        euler.next_to(title, DOWN, buff=1)
        self.play(Write(euler))
        self.wait()

        # Complex plane
        plane = ComplexPlane(
            x_range=[-2, 2],
            y_range=[-2, 2]
        )
        plane.add_coordinate_labels(font_size=20)
        plane.scale(1.5).shift(DOWN)

        self.play(ShowCreation(plane))
        self.wait()

        # Unit circle
        circle = Circle(radius=1.5, color=WHITE)
        circle.move_to(plane.n2p(0))

        # Point on circle
        dot = Dot(color=RED)
        dot.move_to(plane.n2p(1))

        self.play(
            ShowCreation(circle),
            FadeIn(dot, scale=0.5)
        )
        self.wait()

        # Rotate point
        self.play(
            Rotate(dot, PI, about_point=plane.n2p(0)),
            run_time=3
        )
        self.wait()


class MatrixTemplate(Scene):
    """
    Template for matrix operations.
    """

    def construct(self):
        title = Text("Matrix Multiplication", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Create matrices
        matrix_a = Matrix([
            ["a", "b"],
            ["c", "d"]
        ])

        matrix_b = Matrix([
            ["e", "f"],
            ["g", "h"]
        ])

        equals = Tex("=")

        matrix_result = Matrix([
            ["ae+bg", "af+bh"],
            ["ce+dg", "cf+dh"]
        ])

        # Arrange
        group = VGroup(matrix_a, matrix_b, equals, matrix_result)
        group.arrange(RIGHT, buff=0.5)
        group.next_to(title, DOWN, buff=1)

        # Show step by step
        self.play(Write(matrix_a))
        self.wait(0.5)
        self.play(Write(matrix_b))
        self.wait(0.5)
        self.play(Write(equals))
        self.wait(0.5)
        self.play(Write(matrix_result))
        self.wait(2)


if __name__ == "__main__":
    import subprocess
    subprocess.run(["manimgl", __file__, "MathSceneTemplate"])
