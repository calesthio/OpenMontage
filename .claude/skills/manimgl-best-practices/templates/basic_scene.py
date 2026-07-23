"""
Basic Scene Template for ManimGL

This is a standard 2D scene template. Copy and modify for your animations.

Usage:
    manimgl templates/basic_scene.py BasicSceneTemplate
    manimgl templates/basic_scene.py BasicSceneTemplate -l  # Low quality for testing
    manimgl templates/basic_scene.py BasicSceneTemplate -w  # Write to file
"""

from manimlib import *


class BasicSceneTemplate(Scene):
    """
    A basic scene template showing common patterns.

    Modify this template for your needs:
    - Add your mobjects in construct()
    - Create animations with self.play()
    - Use self.wait() for pauses
    """

    def construct(self):
        # === TITLE ===
        title = Text("My Animation", font_size=60)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait()

        # === MAIN CONTENT ===
        # Create your mobjects
        circle = Circle(radius=1.5, color=BLUE)
        circle.set_fill(BLUE, opacity=0.5)
        circle.set_stroke(WHITE, width=3)

        square = Square(side_length=2, color=GREEN)
        square.set_fill(GREEN, opacity=0.5)
        square.set_stroke(WHITE, width=3)
        square.next_to(circle, RIGHT, buff=1)

        # Animate creation
        self.play(
            ShowCreation(circle),
            ShowCreation(square)
        )
        self.wait()

        # === TRANSFORMATIONS ===
        # Transform or animate
        self.play(
            circle.animate.shift(DOWN),
            square.animate.shift(DOWN)
        )
        self.wait()

        # === LABELS ===
        # Add labels
        circle_label = Text("Circle", font_size=36)
        circle_label.next_to(circle, DOWN)

        square_label = Text("Square", font_size=36)
        square_label.next_to(square, DOWN)

        self.play(
            FadeIn(circle_label, shift=UP),
            FadeIn(square_label, shift=UP)
        )
        self.wait()

        # === CLEANUP ===
        # Fade out everything
        self.play(FadeOut(VGroup(
            title, circle, square, circle_label, square_label
        )))
        self.wait()


class MinimalScene(Scene):
    """
    Minimal scene template - just the essentials.
    """

    def construct(self):
        # Your code here
        text = Text("Hello ManimGL!", font_size=72)
        self.play(Write(text))
        self.wait(2)


class AnimationShowcase(Scene):
    """
    Template showing various animation types.
    """

    def construct(self):
        title = Text("Animation Types", font_size=48)
        title.to_edge(UP)
        self.add(title)

        # ShowCreation
        circle = Circle(color=BLUE)
        self.play(ShowCreation(circle))
        self.wait(0.5)
        self.play(FadeOut(circle))

        # Write (for text)
        text = Text("Written Text", font_size=48)
        self.play(Write(text))
        self.wait(0.5)
        self.play(FadeOut(text))

        # FadeIn
        square = Square(color=GREEN)
        self.play(FadeIn(square, scale=0.5))
        self.wait(0.5)
        self.play(FadeOut(square))

        # Transform
        shape1 = Circle(color=YELLOW)
        shape2 = Square(color=RED)
        self.play(ShowCreation(shape1))
        self.play(Transform(shape1, shape2))
        self.wait(0.5)

        self.play(FadeOut(VGroup(title, shape1)))


if __name__ == "__main__":
    # This allows you to run: python basic_scene.py
    # (though using manimgl is recommended)
    import subprocess
    subprocess.run(["manimgl", __file__, "BasicSceneTemplate"])
