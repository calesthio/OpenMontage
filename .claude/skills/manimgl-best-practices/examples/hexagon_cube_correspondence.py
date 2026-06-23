"""
Visualization showing the correspondence between hexagonal tilings
and 3D cube stacking patterns.
"""
from manimlib import *


class HexagonCubeCorrespondence(InteractiveScene):
    """
    Shows how a hexagonal tiling corresponds to viewing 3D cube stacks from above.

    Demonstrates:
    1. Creating half-cube faces in 3D
    2. Viewing them from the [1,1,1] direction
    3. How rotation in 2D corresponds to adding/removing cubes in 3D
    """
    n = 4
    colors = [BLUE_B, BLUE_D, BLUE_E]

    def construct(self):
        # Set up axes and camera angle
        self.frame.set_field_of_view(1 * DEGREES)
        self.frame.reorient(135, 55, 0)
        axes = ThreeDAxes((-5, 5), (-5, 5), (-5, 5))

        # Add base half-cube
        base_cube = self.get_half_cube(
            side_length=self.n,
            shared_corner=[-1, -1, -1],
            grid=True
        )
        self.add(base_cube)

        # Add cubes to build a stack
        cubes = VGroup()
        block_pattern = np.zeros((self.n, self.n, self.n))

        # Build a pyramid-like structure
        for x in range(self.n):
            for y in range(self.n - x):
                for z in range(self.n - x - y):
                    cube = self.get_half_cube((x, y, z))
                    cubes.add(cube)
                    block_pattern[x, y, z] = 1

        self.play(
            LaggedStart(
                (FadeIn(cube, shift=0.25 * IN) for cube in cubes),
                lag_ratio=0.02,
            ),
            run_time=3
        )
        self.wait()

        # Remove the base and color the cubes
        self.play(FadeOut(base_cube))
        cubes.set_fill(BLUE_D)
        self.wait()

        # Rotate to show hexagonal view
        self.play(
            self.frame.animate.reorient(135, 55, 0, ORIGIN, 8).set_field_of_view(1 * DEGREES),
            run_time=2
        )
        self.wait(2)

    def get_half_cube(self, coords=(0, 0, 0), side_length=1, colors=None, shared_corner=[1, 1, 1], grid=False):
        """Create three visible faces of a cube (half-cube) that would be seen from the [1,1,1] direction."""
        if colors is None:
            colors = self.colors
        squares = Square(side_length).replicate(3)
        if grid:
            for square in squares:
                grid_lines = Square(side_length=1).get_grid(side_length, side_length, buff=0)
                grid_lines.move_to(square)
                square.add(grid_lines)
        axes = [OUT, DOWN, LEFT]
        for square, color, axis in zip(squares, colors, axes):
            square.set_fill(color, 1)
            square.set_stroke(color, 0)
            square.rotate(90.1 * DEGREES, axis)
            square.move_to(ORIGIN, shared_corner)
        squares.move_to(coords, np.array([-1, -1, -1]))
        squares.set_stroke(WHITE, 2)
        return squares
