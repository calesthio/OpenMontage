"""
Query/Key Space Mapping Visualization
Shows how embeddings in high-dimensional space get projected to a lower-dimensional
query/key space where dot products measure relevance.
"""

from manimlib import *


class QueryKeySpaceMapping(InteractiveScene):
    def construct(self):
        # Set up 3D view
        self.set_floor_plane("xz")
        frame = self.frame
        frame.set_field_of_view(30 * DEGREES)
        frame.reorient(-30, -5, 0, (2, 1, 0), 4.5)
        frame.add_ambient_rotation(1 * DEGREES)

        # Create 3D axes representing embedding space
        axes_3d = ThreeDAxes((-3, 3), (-3, 3), (-3, 3))
        xz_plane = NumberPlane(
            (-3, 3), (-3, 3),
            background_line_style=dict(
                stroke_color=GREY,
                stroke_width=1,
            ),
            faded_line_ratio=0
        )
        xz_plane.rotate(90 * DEGREES, RIGHT)
        xz_plane.move_to(axes_3d)
        xz_plane.axes.set_opacity(0)
        axes_3d.add(xz_plane)
        axes_3d.set_height(2.5)

        self.add(axes_3d)

        # Create target 2D plane (Query/Key space)
        plane_2d = NumberPlane(
            (-2.5, 2.5), (-2.5, 2.5),
            faded_line_ratio=1,
            background_line_style=dict(
                stroke_color=BLUE,
                stroke_width=1,
                stroke_opacity=0.75
            ),
            faded_line_style=dict(
                stroke_color=BLUE,
                stroke_width=1,
                stroke_opacity=0.25,
            )
        )
        plane_2d.set_height(3.0)
        plane_2d.to_corner(DR)
        plane_2d.fix_in_frame()

        # Arrow showing the mapping
        arrow = Tex(R"\longrightarrow", font_size=72)
        arrow.set_width(1.5)
        arrow.stretch(0.7, 1)
        arrow.next_to(plane_2d, LEFT, buff=0.8)
        arrow.set_color(YELLOW)
        arrow.fix_in_frame()

        # Label for the mapping
        map_label = Tex("W_Q", font_size=60)
        map_label.set_color(YELLOW)
        map_label.next_to(arrow.get_left(), UR, SMALL_BUFF)
        map_label.shift(0.2 * RIGHT)
        map_label.fix_in_frame()

        # Titles
        titles = VGroup(
            Text("Embedding space", font_size=30),
            Text("Query/Key space", font_size=30),
        )
        subtitles = VGroup(
            Text("12,288-dimensional", font_size=22),
            Text("128-dimensional", font_size=22),
        )
        subtitles.set_fill(GREY_B)

        for title, subtitle in zip(titles, subtitles):
            subtitle.next_to(title, DOWN, SMALL_BUFF)
            title.add(subtitle)

        titles[0].to_edge(UL, buff=0.5)
        titles[0].fix_in_frame()
        titles[1].next_to(plane_2d, UP, MED_LARGE_BUFF)
        titles[1].fix_in_frame()

        self.add(plane_2d)
        self.add(arrow)
        self.add(map_label)
        self.add(titles)

        # Create a vector in 3D space
        in_coords = (2, 2.5, 1)
        in_vect = Arrow(axes_3d.get_origin(), axes_3d.c2p(*in_coords), buff=0)
        in_vect.set_stroke(TEAL, 5)

        in_label = Text("\"Creature\"", font_size=20)
        in_label.set_color(TEAL)
        in_label.next_to(in_vect.get_end(), UP, SMALL_BUFF)

        # Create corresponding vector in 2D space
        out_coords = (-1.5, -1)
        out_vect = Arrow(plane_2d.get_origin(), plane_2d.c2p(*out_coords), buff=0)
        out_vect.set_stroke(YELLOW, 4)
        out_vect.fix_in_frame()

        out_label = Text("Query:\nAny adjectives\nbefore me?", font_size=16)
        out_label.next_to(out_vect.get_end(), DOWN, buff=0.15)
        out_label.set_backstroke(BLACK, 3)
        out_label.fix_in_frame()

        # Animate the transformation
        self.play(
            GrowArrow(in_vect),
            FadeInFromPoint(in_label, axes_3d.get_origin()),
            run_time=1.5
        )
        self.wait(2)

        self.play(
            TransformFromCopy(in_vect, out_vect),
            FadeTransform(in_label.copy(), out_label),
            run_time=2,
        )
        self.wait()

        # Show second vector (Key)
        in_coords_2 = (-2, 1, 2)
        in_vect_2 = Arrow(axes_3d.get_origin(), axes_3d.c2p(*in_coords_2), buff=0)
        in_vect_2.set_stroke(BLUE, 5)

        in_label_2 = Text("\"Fluffy\"", font_size=20)
        in_label_2.set_color(BLUE)
        in_label_2.next_to(in_vect_2.get_end(), UP, SMALL_BUFF)

        out_coords_2 = (-1.2, -0.8)
        out_vect_2 = Arrow(plane_2d.get_origin(), plane_2d.c2p(*out_coords_2), buff=0)
        out_vect_2.set_stroke(TEAL, 4)
        out_vect_2.fix_in_frame()

        out_label_2 = Text("Key:\nAdjective at\nposition 1", font_size=16)
        out_label_2.next_to(out_vect_2.get_end(), LEFT, buff=0.15)
        out_label_2.set_backstroke(BLACK, 3)
        out_label_2.fix_in_frame()

        # Change map label to W_K
        map_label_k = Tex("W_K", font_size=60)
        map_label_k.set_color(TEAL)
        map_label_k.move_to(map_label)
        map_label_k.fix_in_frame()

        self.play(
            GrowArrow(in_vect_2),
            FadeInFromPoint(in_label_2, axes_3d.get_origin()),
            FadeTransform(map_label, map_label_k),
            arrow.animate.set_color(TEAL),
            run_time=1.5
        )
        self.wait(2)

        self.play(
            TransformFromCopy(in_vect_2, out_vect_2),
            FadeTransform(in_label_2.copy(), out_label_2),
            run_time=2,
        )
        self.wait()

        # Show dot product in 2D space
        dot_product_label = Tex(R"\vec{Q} \cdot \vec{K}", font_size=36)
        dot_product_label.set_color(WHITE)
        dot_product_label.next_to(plane_2d, DOWN, buff=0.3)
        dot_product_label.fix_in_frame()

        # Highlight the angle between vectors
        angle_arc = Arc(
            start_angle=out_vect.get_angle(),
            angle=out_vect_2.get_angle() - out_vect.get_angle(),
            radius=0.4,
            arc_center=plane_2d.get_origin(),
        )
        angle_arc.set_stroke(WHITE, 2)
        angle_arc.fix_in_frame()

        high_score = Text("High score = relevant!", font_size=24)
        high_score.set_color(GREEN)
        high_score.next_to(dot_product_label, DOWN, SMALL_BUFF)
        high_score.fix_in_frame()

        self.play(
            Write(dot_product_label),
            ShowCreation(angle_arc),
        )
        self.play(Write(high_score))
        self.wait(5)
