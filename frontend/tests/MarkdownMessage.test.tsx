import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownMessage } from "../src/components/MarkdownMessage";

it("renders fenced code safely and keeps HTML and unsafe links inert", () => {
  render(<MarkdownMessage citations={[]} onCitation={() => {}} content={'## Safe heading\n\n```python\nprint("hello")\n```\n\n<script>alert(1)</script> [run](javascript:alert(1))'} />);
  expect(screen.getByRole("heading", { name: "Safe heading" })).toBeVisible();
  expect(screen.getByText('print("hello")')).toBeVisible();
  expect(screen.getByText("<script>alert(1)</script>")).toBeVisible();
  expect(screen.getByText("run")).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(document.querySelector(".markdown-message a")).toBeNull();
});

it("formats simple emphasis and links with safe protocols", () => {
  render(<MarkdownMessage citations={[]} onCitation={() => {}}
    content="A **supported** statement with `code` and [source](https://example.test/source.pdf)." />);
  expect(screen.getByText("supported").tagName).toBe("STRONG");
  expect(screen.getByText("code").tagName).toBe("CODE");
  expect(screen.getByRole("link", { name: "source" })).toHaveAttribute("href", "https://example.test/source.pdf");
});
