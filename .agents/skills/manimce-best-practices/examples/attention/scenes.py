"""
Attention Mechanism Visualization - Converted from 3b1b ManimGL to ManimCE

Original: videos/_2024/transformers/attention.py
Demonstrates the attention mechanism used in transformers.

Run with: manim -pql scenes.py SceneName
"""

from manim import *
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path for helpers import
sys.path.insert(0, str(Path(__file__).parent))
from helpers import (
    NumericEmbedding, WeightMatrix, ContextAnimation,
    softmax
)


class AttentionPatterns(Scene):
    """
    Demonstrates how attention allows words to influence each other.
    Shows adjectives modifying nouns through attention connections.
    """

    def construct(self):
        # Add sentence
        phrase = "a fluffy blue creature roamed the verdant forest"
        phrase_mob = Text(phrase, font_size=36)
        phrase_mob.move_to(2 * UP)

        words = phrase.split()
        word_mobs = VGroup()

        # Create individual word mobjects
        current_x = phrase_mob.get_left()[0]
        for word in words:
            # Find the word in the phrase
            word_mob = Text(word, font_size=36)
            word_mobs.add(word_mob)

        word_mobs.arrange(RIGHT, buff=0.3)
        word_mobs.move_to(2 * UP)

        self.play(
            LaggedStart(*[FadeIn(w, shift=0.5 * UP) for w in word_mobs], lag_ratio=0.15)
        )
        self.wait()

        # Create word rectangles
        word_rects = VGroup()
        for word_mob in word_mobs:
            rect = SurroundingRectangle(word_mob, buff=0.1)
            rect.set_stroke(GREY, 2)
            rect.set_fill(GREY, 0.2)
            word_rects.add(rect)

        # Identify adjectives and nouns
        adj_indices = [1, 2, 6]  # fluffy, blue, verdant
        noun_indices = [3, 7]     # creature, forest

        adj_rects = VGroup(*[word_rects[i] for i in adj_indices])
        noun_rects = VGroup(*[word_rects[i] for i in noun_indices])

        adj_mobs = VGroup(*[word_mobs[i] for i in adj_indices])
        noun_mobs = VGroup(*[word_mobs[i] for i in noun_indices])

        # Color the rectangles
        adj_rects[0].set_fill(BLUE_C, 0.3)
        adj_rects[1].set_fill(BLUE_D, 0.3)
        adj_rects[2].set_fill(GREEN, 0.3)
        noun_rects.set_fill(GREY_BROWN, 0.3)

        self.play(
            LaggedStart(*[DrawBorderThenFill(r) for r in adj_rects], lag_ratio=0.2),
        )
        self.wait()

        # Show arrows from adjectives to nouns
        adj_arrows = VGroup(
            CurvedArrow(adj_mobs[0].get_top(), noun_mobs[0].get_top(), angle=-0.5),
            CurvedArrow(adj_mobs[1].get_top(), noun_mobs[0].get_top(), angle=-0.5),
            CurvedArrow(adj_mobs[2].get_top(), noun_mobs[1].get_top(), angle=-0.5),
        )
        adj_arrows.set_color(GREY_B)

        self.play(
            LaggedStart(*[DrawBorderThenFill(r) for r in noun_rects], lag_ratio=0.2),
            LaggedStart(*[Create(a) for a in adj_arrows], lag_ratio=0.2),
        )
        self.wait()

        # Animate context flow
        self.play(
            ContextAnimation(noun_mobs[0], adj_mobs[:2], strengths=[1, 1]),
            ContextAnimation(noun_mobs[1], adj_mobs[2:], strengths=[1]),
        )
        self.wait()

        # Show embeddings
        all_rects = word_rects.copy()
        embeddings = VGroup()
        for rect in all_rects:
            emb = NumericEmbedding(length=8)
            emb.set_width(0.4)
            emb.next_to(rect, DOWN, buff=1.2)
            embeddings.add(emb)

        emb_arrows = VGroup()
        for rect, emb in zip(all_rects, embeddings):
            arrow = Arrow(rect.get_bottom(), emb.get_top(), buff=0.1)
            emb_arrows.add(arrow)

        self.play(
            FadeIn(word_rects),
            LaggedStart(*[GrowArrow(a) for a in emb_arrows], lag_ratio=0.1),
            LaggedStart(*[FadeIn(e, shift=0.5 * DOWN) for e in embeddings], lag_ratio=0.1),
            FadeOut(adj_arrows)
        )
        self.wait()

        # Show embedding dimension
        brace = Brace(embeddings[0], LEFT, buff=SMALL_BUFF)
        dim_label = Text("12,288", font_size=24, color=YELLOW)
        dim_label.next_to(brace, LEFT)

        self.play(
            GrowFromCenter(brace),
            FadeIn(dim_label)
        )
        self.wait(2)


class QueryKeyValueExplanation(Scene):
    """
    Explains the Query, Key, Value mechanism in attention.
    """

    def construct(self):
        # Title
        title = Text("Query, Key, Value", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait()

        # Create three matrices
        q_matrix = WeightMatrix(shape=(4, 4), value_range=(-5, 5))
        k_matrix = WeightMatrix(shape=(4, 4), value_range=(-5, 5))
        v_matrix = WeightMatrix(shape=(4, 4), value_range=(-5, 5))

        matrices = VGroup(q_matrix, k_matrix, v_matrix)
        matrices.arrange(RIGHT, buff=1)
        matrices.set_height(2)
        matrices.next_to(title, DOWN, buff=0.8)

        # Labels
        q_label = Text("Query (Q)", font_size=30, color=BLUE)
        k_label = Text("Key (K)", font_size=30, color=GREEN)
        v_label = Text("Value (V)", font_size=30, color=RED)

        q_label.next_to(q_matrix, UP)
        k_label.next_to(k_matrix, UP)
        v_label.next_to(v_matrix, UP)

        self.play(
            FadeIn(q_matrix),
            Write(q_label),
        )
        self.wait()

        self.play(
            FadeIn(k_matrix),
            Write(k_label),
        )
        self.wait()

        self.play(
            FadeIn(v_matrix),
            Write(v_label),
        )
        self.wait()

        # Explain the formula
        formula = MathTex(
            r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V",
            font_size=36
        )
        formula.next_to(matrices, DOWN, buff=1)

        self.play(Write(formula))
        self.wait(2)

        # Highlight different parts
        # Q*K^T computes similarity
        explanation1 = Text("Q·K^T → measures similarity between queries and keys", font_size=24)
        explanation1.next_to(formula, DOWN, buff=0.5)

        self.play(Write(explanation1))
        self.wait()

        # Softmax normalizes
        explanation2 = Text("Softmax → converts to attention weights (probabilities)", font_size=24)
        explanation2.next_to(explanation1, DOWN, buff=0.3)

        self.play(Write(explanation2))
        self.wait()

        # Multiply by V
        explanation3 = Text("× V → weighted sum of values", font_size=24)
        explanation3.next_to(explanation2, DOWN, buff=0.3)

        self.play(Write(explanation3))
        self.wait(2)


class AttentionMatrixVisualization(Scene):
    """
    Shows how attention scores form a matrix pattern.
    """

    def construct(self):
        # Create tokens
        tokens = ["The", "cat", "sat", "on", "the", "mat"]
        n = len(tokens)

        # Token labels on left (queries)
        query_labels = VGroup(*[Text(t, font_size=24) for t in tokens])
        query_labels.arrange(DOWN, buff=0.4)
        query_labels.shift(LEFT * 4)

        # Token labels on top (keys)
        key_labels = VGroup(*[Text(t, font_size=24) for t in tokens])
        key_labels.arrange(RIGHT, buff=0.4)
        key_labels.next_to(query_labels, RIGHT, buff=1)
        key_labels.shift(UP * 2)

        # Create attention grid
        attention_scores = softmax(np.random.randn(n, n) * 2, temperature=0.3)

        grid = VGroup()
        for i in range(n):
            row = VGroup()
            for j in range(n):
                score = attention_scores[i, j]
                cell = Square(side_length=0.5)
                cell.set_fill(
                    color=interpolate_color(BLACK, YELLOW, score),
                    opacity=0.8
                )
                cell.set_stroke(WHITE, 0.5)
                row.add(cell)
            row.arrange(RIGHT, buff=0)
            grid.add(row)

        grid.arrange(DOWN, buff=0)
        grid.next_to(query_labels, RIGHT, buff=0.5)
        grid.align_to(query_labels, UP)

        # Adjust key labels position
        key_labels.move_to(grid.get_top() + UP * 0.5)
        key_labels.align_to(grid, LEFT)

        # Title
        title = Text("Attention Matrix", font_size=36)
        title.to_edge(UP)

        self.play(Write(title))
        self.play(
            LaggedStart(*[FadeIn(l) for l in query_labels], lag_ratio=0.1),
            LaggedStart(*[FadeIn(l) for l in key_labels], lag_ratio=0.1),
        )
        self.wait()

        # Animate grid appearing
        all_cells = VGroup(*[cell for row in grid for cell in row])
        self.play(
            LaggedStart(*[FadeIn(c, scale=0.5) for c in all_cells], lag_ratio=0.02)
        )
        self.wait()

        # Highlight a row (how "cat" attends to all words)
        highlight_row = 1  # "cat"
        row_highlight = SurroundingRectangle(grid[highlight_row], color=BLUE, buff=0.05)

        explanation = Text(
            '"cat" attends mostly to itself and "sat"',
            font_size=24
        )
        explanation.next_to(grid, DOWN, buff=0.5)

        self.play(Create(row_highlight), Write(explanation))
        self.wait(2)


class MultiHeadedAttention(ThreeDScene):
    """
    Explains multi-head attention mechanism with 3D visualization.
    Shows multiple attention heads arranged in depth with camera rotation.
    Inspired by 3b1b's transformer visualization.
    """

    def construct(self):
        # Title animation: Single head -> Multi-head
        single_title = Text("Single head of attention", font_size=42)
        multiple_title = Text("Multi-headed attention", font_size=42)

        for title in [single_title, multiple_title]:
            title.to_edge(UP)

        self.play(Write(single_title))
        self.wait(0.5)

        # Flash around "head"
        head_text = single_title[7:11]  # "head"
        self.play(
            Indicate(head_text, color=YELLOW, scale_factor=1.2),
            head_text.animate.set_color(YELLOW),
        )
        self.wait(0.5)

        # Transform title
        self.play(
            TransformMatchingShapes(single_title, multiple_title),
            run_time=1.5
        )
        self.wait()

        # Create attention pattern visualization (grid with dots)
        def create_attention_pattern(n_rows=8, seed=None):
            """Create a grid visualization of attention weights."""
            if seed is not None:
                np.random.seed(seed)

            # Create the base grid
            grid = VGroup()
            cell_size = 0.4
            for i in range(n_rows):
                for j in range(n_rows):
                    cell = Square(side_length=cell_size)
                    cell.set_stroke(WHITE, 0.5, opacity=0.3)
                    cell.move_to(np.array([j * cell_size, -i * cell_size, 0]))
                    grid.add(cell)

            grid.center()

            # Generate causal attention pattern (lower triangular)
            pattern = np.random.normal(0, 1, (n_rows, n_rows))
            for n in range(n_rows):
                pattern[:, n][n + 1:] = -np.inf  # Mask future tokens
                exp_vals = np.exp(pattern[:, n] - np.max(pattern[:, n][pattern[:, n] > -np.inf]))
                pattern[:, n] = exp_vals / np.sum(exp_vals[exp_vals < np.inf])
            pattern = np.nan_to_num(pattern, nan=0.0, posinf=0.0, neginf=0.0)

            # Add dots based on attention weights
            dots = VGroup()
            for i in range(n_rows):
                for j in range(n_rows):
                    value = pattern[i, j]
                    if value > 0.05:  # Threshold for visibility
                        dot = Dot(
                            radius=cell_size * 0.4 * value,
                            color=GREY_B,
                            fill_opacity=0.8
                        )
                        dot.move_to(grid[i * n_rows + j].get_center())
                        dots.add(dot)

            # Create border rectangle
            border = SurroundingRectangle(grid, buff=0.05)
            border.set_stroke(WHITE, 2)
            border.set_fill(BLACK, 0.9)

            pattern_mob = VGroup(border, grid, dots)
            return pattern_mob

        # Create multiple attention heads
        n_heads = 12
        heads = VGroup()
        for i in range(n_heads):
            head = create_attention_pattern(n_rows=6, seed=i * 42)
            head.set_height(2.5)
            heads.add(head)

        # Arrange in 3D depth (along z-axis)
        for i, head in enumerate(heads):
            head.shift(OUT * i * 0.5)  # Stack in z direction

        heads.center()
        heads.shift(DOWN * 0.5)

        # Show first head (screen rectangle style)
        first_head = heads[-1].copy()
        first_head.move_to(ORIGIN + DOWN * 0.5)
        first_head.shift(IN * (n_heads - 1) * 0.25)  # Reset z position

        self.play(FadeIn(first_head))
        self.wait()

        # Add fixed-in-frame elements
        self.add_fixed_in_frame_mobjects(multiple_title)

        # Rotate camera to reveal depth
        self.move_camera(
            phi=70 * DEGREES,
            theta=-60 * DEGREES,
            run_time=2
        )

        # Fan out the heads from the first one
        self.play(
            LaggedStart(
                *[FadeIn(head, shift=OUT * 0.3) for head in heads[:-1]],
                lag_ratio=0.15
            ),
            FadeOut(first_head),
            run_time=3
        )
        self.add(heads)
        self.wait()

        # Add matrix labels for each head (W_Q, W_K)
        wq_labels = VGroup()
        wk_labels = VGroup()

        colors = [YELLOW, TEAL]
        n_shown = min(5, n_heads)

        for i, head in enumerate(list(heads)[-n_shown:]):
            head_num = n_heads - n_shown + i + 1
            wq = MathTex(f"W_Q^{{({head_num})}}", font_size=28, color=YELLOW)
            wk = MathTex(f"W_K^{{({head_num})}}", font_size=28, color=TEAL)

            # Position above each head
            wq.next_to(head, UP, buff=0.2)
            wq.shift(LEFT * 0.3)
            wk.next_to(head, UP, buff=0.2)
            wk.shift(RIGHT * 0.3)

            # Rotate to face camera
            for label in [wq, wk]:
                label.rotate(70 * DEGREES, axis=RIGHT)
                label.rotate(-60 * DEGREES, axis=OUT)

            wq_labels.add(wq)
            wk_labels.add(wk)

        # Add dots to indicate more heads
        dots_label = MathTex(r"\cdots", font_size=48, color=WHITE)
        dots_label.next_to(heads[0], OUT, buff=0.5)
        dots_label.rotate(70 * DEGREES, axis=RIGHT)
        dots_label.rotate(-60 * DEGREES, axis=OUT)

        self.play(
            LaggedStart(*[FadeIn(wq, shift=UP * 0.2) for wq in wq_labels], lag_ratio=0.2),
            run_time=1.5
        )
        self.play(
            LaggedStart(*[FadeIn(wk, shift=UP * 0.2) for wk in wk_labels], lag_ratio=0.2),
            FadeIn(dots_label),
            run_time=1.5
        )
        self.wait()

        # Add brace showing "96 heads" (scaled down for demonstration)
        brace_text = Text("96 heads", font_size=36, color=WHITE)
        brace_text.rotate(70 * DEGREES, axis=RIGHT)
        brace_text.rotate(-60 * DEGREES, axis=OUT)
        brace_text.next_to(heads, UP, buff=0.8)
        brace_text.shift(LEFT * 2)

        self.play(FadeIn(brace_text, shift=UP * 0.3))
        self.wait()

        # Rotate camera to show different angle
        self.move_camera(
            phi=60 * DEGREES,
            theta=-80 * DEGREES,
            run_time=2
        )
        self.wait()

        # Explanation text (fixed in frame)
        explanation = VGroup(
            Text("Each head learns different patterns:", font_size=24),
            Text("• Syntactic relationships", font_size=20, color=BLUE),
            Text("• Semantic connections", font_size=20, color=GREEN),
            Text("• Positional patterns", font_size=20, color=YELLOW),
        )
        explanation.arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        explanation.to_corner(DL, buff=0.5)

        self.add_fixed_in_frame_mobjects(explanation)
        self.play(
            LaggedStart(*[Write(e) for e in explanation], lag_ratio=0.3)
        )
        self.wait()

        # Return to front view
        self.move_camera(
            phi=0,
            theta=-90 * DEGREES,
            run_time=2
        )
        self.wait()

        # Show concatenation concept
        concat_text = Text("Concatenate outputs from all heads", font_size=28)
        concat_text.to_edge(DOWN, buff=0.5)
        self.add_fixed_in_frame_mobjects(concat_text)
        self.play(Write(concat_text))
        self.wait()

        # Final hold
        self.wait()
        self.wait(2)


class SelfAttentionDemo(Scene):
    """
    Interactive demonstration of self-attention on a simple sentence.
    """

    def construct(self):
        # Title
        title = Text("Self-Attention in Action", font_size=42)
        title.to_edge(UP)
        self.play(Write(title))

        # Create sentence
        sentence = "The quick brown fox"
        words = sentence.split()

        word_boxes = VGroup()
        for word in words:
            box = VGroup(
                RoundedRectangle(
                    width=1.5, height=0.8,
                    corner_radius=0.1,
                    fill_opacity=0.3,
                    fill_color=BLUE,
                    stroke_color=WHITE
                ),
                Text(word, font_size=28)
            )
            box[1].move_to(box[0])
            word_boxes.add(box)

        word_boxes.arrange(RIGHT, buff=0.5)
        word_boxes.next_to(title, DOWN, buff=1)

        self.play(
            LaggedStart(*[FadeIn(b, scale=0.8) for b in word_boxes], lag_ratio=0.2)
        )
        self.wait()

        # Show attention from "fox" to other words
        target_idx = 3  # "fox"
        attention_weights = [0.1, 0.3, 0.4, 0.2]  # Attention weights

        # Highlight target
        target_box = word_boxes[target_idx]
        target_highlight = SurroundingRectangle(target_box, color=YELLOW, buff=0.1)

        self.play(Create(target_highlight))

        # Create attention arrows
        attention_arrows = VGroup()
        weight_labels = VGroup()

        for i, (box, weight) in enumerate(zip(word_boxes, attention_weights)):
            if i != target_idx:
                arrow = CurvedArrow(
                    box.get_bottom() + DOWN * 0.1,
                    target_box.get_bottom() + DOWN * 0.1,
                    angle=0.5 if i < target_idx else -0.5
                )
                arrow.set_stroke(
                    color=interpolate_color(GREY, YELLOW, weight),
                    width=weight * 8
                )
                attention_arrows.add(arrow)

                label = DecimalNumber(weight, num_decimal_places=1, font_size=20)
                label.next_to(arrow.point_from_proportion(0.5), DOWN, buff=0.1)
                weight_labels.add(label)

        self.play(
            LaggedStart(*[Create(a) for a in attention_arrows], lag_ratio=0.2),
            LaggedStart(*[FadeIn(l) for l in weight_labels], lag_ratio=0.2),
        )
        self.wait()

        # Show weighted combination
        result_text = Text(
            '"fox" = 0.1×"The" + 0.3×"quick" + 0.4×"brown" + 0.2×"fox"',
            font_size=24
        )
        result_text.next_to(word_boxes, DOWN, buff=1.5)

        self.play(Write(result_text))
        self.wait(2)


class ScaledDotProductAttention(Scene):
    """
    Step-by-step visualization of scaled dot-product attention.
    """

    def construct(self):
        # Title
        title = Text("Scaled Dot-Product Attention", font_size=40)
        title.to_edge(UP)
        self.play(Write(title))

        # Step 1: Show Q, K, V
        step1 = Text("Step 1: Compute Q, K, V from input", font_size=28)
        step1.next_to(title, DOWN, buff=0.5)

        q_vec = NumericEmbedding(length=4).set_height(1.5)
        k_vec = NumericEmbedding(length=4).set_height(1.5)
        v_vec = NumericEmbedding(length=4).set_height(1.5)

        vectors = VGroup(q_vec, k_vec, v_vec)
        vectors.arrange(RIGHT, buff=1)
        vectors.next_to(step1, DOWN, buff=0.5)

        q_label = Text("Q", color=BLUE, font_size=24).next_to(q_vec, UP)
        k_label = Text("K", color=GREEN, font_size=24).next_to(k_vec, UP)
        v_label = Text("V", color=RED, font_size=24).next_to(v_vec, UP)

        self.play(Write(step1))
        self.play(
            FadeIn(q_vec), FadeIn(k_vec), FadeIn(v_vec),
            Write(q_label), Write(k_label), Write(v_label)
        )
        self.wait()

        # Step 2: Compute Q·K^T
        self.play(
            FadeOut(step1),
            VGroup(vectors, q_label, k_label, v_label).animate.shift(UP)
        )

        step2 = Text("Step 2: Q · K^T (dot product)", font_size=28)
        step2.next_to(title, DOWN, buff=0.5)

        dot_product = MathTex(r"Q \cdot K^T = ", font_size=36)
        score = DecimalNumber(2.5, font_size=36, color=YELLOW)
        dot_result = VGroup(dot_product, score).arrange(RIGHT)
        dot_result.next_to(vectors, DOWN, buff=0.5)

        self.play(Write(step2))
        self.play(Write(dot_product), FadeIn(score))
        self.wait()

        # Step 3: Scale
        self.play(FadeOut(step2))
        step3 = Text("Step 3: Scale by √d_k", font_size=28)
        step3.next_to(title, DOWN, buff=0.5)

        scale_formula = MathTex(r"\frac{Q \cdot K^T}{\sqrt{d_k}} = \frac{2.5}{\sqrt{4}} = 1.25", font_size=32)
        scale_formula.next_to(dot_result, DOWN, buff=0.3)

        self.play(Write(step3))
        self.play(Write(scale_formula))
        self.wait()

        # Step 4: Softmax
        self.play(FadeOut(step3))
        step4 = Text("Step 4: Softmax → attention weights", font_size=28)
        step4.next_to(title, DOWN, buff=0.5)

        softmax_text = MathTex(r"\text{softmax}(1.25) \rightarrow \text{weights}", font_size=32)
        softmax_text.next_to(scale_formula, DOWN, buff=0.3)

        self.play(Write(step4))
        self.play(Write(softmax_text))
        self.wait()

        # Step 5: Multiply by V
        self.play(FadeOut(step4))
        step5 = Text("Step 5: Weighted sum of V", font_size=28)
        step5.next_to(title, DOWN, buff=0.5)

        final = MathTex(r"\text{Output} = \text{weights} \times V", font_size=32)
        final.next_to(softmax_text, DOWN, buff=0.3)

        self.play(Write(step5))
        self.play(Write(final))
        self.wait(2)


class PositionalEncoding(Scene):
    """
    Explains positional encoding in transformers.
    """

    def construct(self):
        title = Text("Positional Encoding", font_size=42)
        title.to_edge(UP)
        self.play(Write(title))

        # Problem statement
        problem = Text(
            "Problem: Attention has no sense of word order!",
            font_size=28, color=RED
        )
        problem.next_to(title, DOWN, buff=0.5)
        self.play(Write(problem))
        self.wait()

        # Show two sentences
        sent1 = Text('"The cat ate the fish"', font_size=24)
        sent2 = Text('"The fish ate the cat"', font_size=24)
        sents = VGroup(sent1, sent2).arrange(DOWN, buff=0.3)
        sents.next_to(problem, DOWN, buff=0.5)

        self.play(Write(sent1), Write(sent2))
        self.wait()

        # Show they have same words
        same = Text("Same words, different meanings!", font_size=24, color=YELLOW)
        same.next_to(sents, DOWN, buff=0.3)
        self.play(Write(same))
        self.wait()

        # Solution
        self.play(FadeOut(problem), FadeOut(sents), FadeOut(same))

        solution = Text(
            "Solution: Add position information to embeddings",
            font_size=28, color=GREEN
        )
        solution.next_to(title, DOWN, buff=0.5)
        self.play(Write(solution))

        # Show formula
        formula = MathTex(
            r"PE_{(pos, 2i)} &= \sin\left(\frac{pos}{10000^{2i/d}}\right) \\",
            r"PE_{(pos, 2i+1)} &= \cos\left(\frac{pos}{10000^{2i/d}}\right)",
            font_size=32
        )
        formula.next_to(solution, DOWN, buff=0.5)
        self.play(Write(formula))
        self.wait()

        # Visual representation
        positions = VGroup()
        for i in range(5):
            pos_vec = VGroup()
            for j in range(8):
                val = np.sin(i / (10000 ** (j / 8))) if j % 2 == 0 else np.cos(i / (10000 ** (j / 8)))
                cell = Square(side_length=0.3)
                cell.set_fill(interpolate_color(BLUE, RED, (val + 1) / 2), opacity=0.8)
                cell.set_stroke(WHITE, 0.5)
                pos_vec.add(cell)
            pos_vec.arrange(DOWN, buff=0)
            positions.add(pos_vec)

        positions.arrange(RIGHT, buff=0.2)
        positions.set_height(2)
        positions.next_to(formula, DOWN, buff=0.5)

        pos_labels = VGroup(*[
            Text(f"pos={i}", font_size=16).next_to(p, DOWN, buff=0.1)
            for i, p in enumerate(positions)
        ])

        self.play(
            LaggedStart(*[FadeIn(p) for p in positions], lag_ratio=0.1),
            LaggedStart(*[FadeIn(l) for l in pos_labels], lag_ratio=0.1),
        )
        self.wait(2)


# Additional simplified scenes for the key concepts

class WhatIsAttention(Scene):
    """Simple introduction to attention."""

    def construct(self):
        title = Text("What is Attention?", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Key idea
        idea = Text(
            "Attention lets each word look at other words\nto understand context",
            font_size=32, line_spacing=1.5
        )
        idea.next_to(title, DOWN, buff=1)
        self.play(Write(idea))
        self.wait()

        # Example
        example_sentence = Text("The bank was steep", font_size=36)
        example_sentence.next_to(idea, DOWN, buff=1)

        self.play(Write(example_sentence))
        self.wait()

        # Highlight "bank" and "steep"
        bank_box = SurroundingRectangle(
            example_sentence[4:8],  # "bank"
            color=YELLOW, buff=0.05
        )
        steep_box = SurroundingRectangle(
            example_sentence[13:18],  # "steep"
            color=GREEN, buff=0.05
        )

        self.play(Create(bank_box))
        self.wait()

        arrow = CurvedArrow(
            steep_box.get_top(),
            bank_box.get_top(),
            angle=-0.5,
            color=YELLOW
        )

        self.play(Create(steep_box), Create(arrow))

        meaning = Text(
            '"steep" helps us know "bank" means riverbank, not financial bank',
            font_size=24, color=GREY_B
        )
        meaning.next_to(example_sentence, DOWN, buff=0.8)
        self.play(Write(meaning))
        self.wait(2)
