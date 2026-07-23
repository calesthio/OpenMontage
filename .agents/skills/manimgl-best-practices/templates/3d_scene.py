"""
3D Scene Template for ManimGL

Template for creating 3D animations with camera control.

Usage:
    manimgl templates/3d_scene.py ThreeDSceneTemplate
    manimgl templates/3d_scene.py ThreeDSceneTemplate -l  # Low quality
    manimgl templates/3d_scene.py ThreeDSceneTemplate -se 20  # Interactive at line 20
"""

from manimlib import *


class ThreeDSceneTemplate(Scene):
    """
    Basic 3D scene template.

    Key concepts:
    - Use self.camera.frame (or self.frame) for camera control
    - frame.reorient(theta, phi) sets camera orientation
    - Use fix_in_frame() for 2D labels that don't rotate
    - Press 'd' + mouse to rotate camera interactively (with touch())
    """

    def construct(self):
        # === CAMERA SETUP ===
        frame = self.camera.frame

        # Set initial 3D orientation
        # theta: rotation around z-axis (azimuthal)
        # phi: angle from z-axis (polar)
        frame.reorient(20, 70)  # Good default for isometric view

        # === TITLE (Fixed in frame) ===
        title = Text("3D Visualization", font_size=48)
        title.to_edge(UP)
        title.fix_in_frame()  # Stays in screen space
        title.set_backstroke(BLACK, width=5)
        self.add(title)

        # === 3D AXES ===
        axes = ThreeDAxes(
            x_range=(-3, 3, 1),
            y_range=(-3, 3, 1),
            z_range=(-3, 3, 1),
            width=8,
            height=8,
            depth=8
        )
        axes.add_coordinate_labels(font_size=20)
        self.play(ShowCreation(axes))
        self.wait()

        # === 3D OBJECTS ===
        # Sphere
        sphere = Sphere(radius=1.5, color=BLUE, resolution=(20, 20))
        sphere.set_opacity(0.7)
        sphere.shift(LEFT * 2)

        # Cube
        cube = Cube(side_length=2, color=GREEN)
        cube.set_opacity(0.8)
        cube.shift(RIGHT * 2)

        # Create objects
        self.play(
            ShowCreation(sphere),
            ShowCreation(cube)
        )
        self.wait()

        # === CAMERA ANIMATION ===
        # Rotate camera around scene
        self.play(
            frame.animate.reorient(45, 80),
            run_time=3
        )
        self.wait()

        # === CONTINUOUS ROTATION ===
        # Add updater for continuous rotation
        frame.add_updater(lambda m, dt: m.increment_theta(20 * dt))
        self.wait(5)
        frame.clear_updaters()

        # === CLEANUP ===
        self.play(
            FadeOut(axes),
            FadeOut(sphere),
            FadeOut(cube),
            FadeOut(title)
        )
        self.wait()


class ParametricSurfaceTemplate(Scene):
    """
    Template for parametric 3D surfaces.
    """

    def construct(self):
        frame = self.camera.frame
        frame.reorient(30, 75)

        # Title
        title = Text("Parametric Surface", font_size=48)
        title.to_edge(UP)
        title.fix_in_frame()
        self.add(title)

        # Create parametric surface
        surface = ParametricSurface(
            lambda u, v: np.array([
                u,
                v,
                np.sin(np.sqrt(u**2 + v**2))  # Sinc function
            ]),
            u_range=(-3, 3),
            v_range=(-3, 3),
            resolution=(30, 30)
        )
        surface.set_color(BLUE)
        surface.set_opacity(0.7)

        # Optional: Add mesh overlay
        mesh = SurfaceMesh(surface)
        mesh.set_stroke(WHITE, width=0.5, opacity=0.3)

        # Show surface
        self.play(
            ShowCreation(surface),
            ShowCreation(mesh),
            run_time=3
        )
        self.wait()

        # Rotate camera
        self.play(
            frame.animate.increment_theta(180 * DEGREES),
            run_time=6
        )
        self.wait()


class Interactive3DTemplate(Scene):
    """
    Template for interactive 3D exploration.

    Use with: manimgl templates/3d_scene.py Interactive3DTemplate -se 30
    Then use touch() in the shell to interact with the scene.
    """

    def construct(self):
        frame = self.camera.frame
        frame.reorient(20, 70)

        # Create 3D content
        sphere = Sphere(radius=2, color=BLUE)
        sphere.set_gloss(0.8)

        cube = Cube(side_length=1.5, color=GREEN)
        cube.shift(RIGHT * 3)

        torus = Torus(r1=1.5, r2=0.5, color=YELLOW)
        torus.shift(LEFT * 3)

        self.play(
            ShowCreation(sphere),
            ShowCreation(cube),
            ShowCreation(torus)
        )
        self.wait()

        # === INTERACTIVE MODE ===
        # Uncomment this to enter interactive mode
        # self.embed()

        # In the shell, try:
        # >>> touch()
        # Then use:
        #   'd' + mouse to rotate
        #   'z' + scroll to zoom
        #   'r' to reset camera
        #   'q' to quit touch mode


class TexturedSphereTemplate(Scene):
    """
    Template for 3D objects with textures.
    """

    def construct(self):
        frame = self.camera.frame
        frame.reorient(20, 70)

        title = Text("Textured Sphere", font_size=48)
        title.to_edge(UP)
        title.fix_in_frame()
        self.add(title)

        # Create sphere
        sphere = Sphere(radius=2, resolution=(40, 40))

        # Apply texture (can use URL or local file)
        # Example with Earth texture
        textured_sphere = TexturedSurface(
            sphere,
            "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Whole_world_-_land_and_oceans.jpg/1280px-Whole_world_-_land_and_oceans.jpg"
        )

        self.add(textured_sphere)
        self.wait()

        # Rotate to show texture
        self.play(
            frame.animate.increment_theta(360 * DEGREES),
            run_time=10,
            rate_func=linear
        )


class LightingTemplate(Scene):
    """
    Template demonstrating lighting effects in 3D.
    """

    def construct(self):
        frame = self.camera.frame
        frame.reorient(30, 70)

        # Create glossy sphere
        sphere = Sphere(radius=2, color=BLUE)
        sphere.set_gloss(0.9)  # High gloss for shininess
        sphere.set_shadow(0.5)  # Add shadow

        self.add(sphere)
        self.wait()

        # Access and move light source
        light = self.camera.light_source

        # Animate light position
        self.play(light.animate.move_to([5, 5, 5]), run_time=2)
        self.wait()
        self.play(light.animate.move_to([-5, -5, 5]), run_time=2)
        self.wait()

        # Rotate camera
        self.play(
            frame.animate.increment_theta(180 * DEGREES),
            run_time=4
        )


if __name__ == "__main__":
    import subprocess
    subprocess.run(["manimgl", __file__, "ThreeDSceneTemplate"])
