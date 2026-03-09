function postProcessBlocks(rawBlocks) {
  const normalized = [];
  let lastText = "";

  for (const block of rawBlocks) {
    const text = String(block.text || "").replace(/\s+/g, " ").trim();

    if (!text || text === lastText) {
      continue;
    }

    lastText = text;
    normalized.push({
      index: normalized.length,
      type: block.type,
      level: block.level || 0,
      tag: block.tag || "",
      text
    });
  }

  return normalized;
}

export async function extractStructuredDocument(page) {
  const raw = await page.evaluate(() => {
    const rootSelectors = [
      "[role='main']",
      "main",
      "[data-page-root]",
      "[data-testid*='document']",
      ".wiki-content",
      ".docs-page",
      "body"
    ];
    const root =
      rootSelectors
        .map((selector) => document.querySelector(selector))
        .find(Boolean) || document.body;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const blocks = [];
    const seen = new Map();
    const unsupportedSelectors = [
      { type: "table", selector: "table,[data-block-type='table']" },
      { type: "image", selector: "img,[data-block-type='image']" },
      { type: "code", selector: "pre,[data-block-type='code']" },
      { type: "fold", selector: "[data-block-type='fold'],[data-block-type='toggle']" },
      { type: "embed", selector: "iframe,video,[data-block-type='embed']" }
    ];

    function isVisible(element) {
      if (!element) {
        return false;
      }

      const style = window.getComputedStyle(element);
      if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        Number(style.opacity) === 0
      ) {
        return false;
      }

      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }

    function findBlock(textNode) {
      let element = textNode.parentElement;

      while (element && element !== root) {
        const style = window.getComputedStyle(element);
        const role = element.getAttribute("role");
        const tag = element.tagName;
        const blockLike =
          /^H[1-6]$/.test(tag) ||
          ["P", "LI", "BLOCKQUOTE", "PRE", "TD", "TH"].includes(tag) ||
          element.hasAttribute("data-block-id") ||
          element.hasAttribute("data-node-key") ||
          ["block", "list-item", "table-row", "flex"].includes(style.display) ||
          role === "heading" ||
          role === "listitem";

        if (blockLike && isVisible(element)) {
          return element;
        }

        element = element.parentElement;
      }

      return root;
    }

    function classify(element, text) {
      const tag = element.tagName.toLowerCase();
      const role = element.getAttribute("role");
      const fontSize = Number.parseFloat(window.getComputedStyle(element).fontSize || "0");
      let type = "paragraph";
      let level = 0;

      if (/^h[1-6]$/.test(tag)) {
        type = "heading";
        level = Number(tag.slice(1));
      } else if (role === "heading") {
        type = "heading";
        level = Number(element.getAttribute("aria-level") || 2);
      } else if (tag === "li" || role === "listitem" || /^[-*•]\s/.test(text)) {
        type = "list_item";
      } else if (tag === "blockquote") {
        type = "quote";
      } else if (tag === "pre") {
        type = "code";
      } else if (fontSize >= 22 && text.length <= 40) {
        type = "heading";
        level = 2;
      }

      return {
        type,
        level,
        tag,
        text
      };
    }

    let currentNode;

    while ((currentNode = walker.nextNode())) {
      const text = currentNode.textContent?.replace(/\s+/g, " ").trim() || "";

      if (!text) {
        continue;
      }

      const blockElement = findBlock(currentNode);

      if (!blockElement || !isVisible(blockElement)) {
        continue;
      }

      if (!seen.has(blockElement)) {
        seen.set(blockElement, {
          element: blockElement,
          texts: []
        });
        blocks.push(seen.get(blockElement));
      }

      seen.get(blockElement).texts.push(text);
    }

    const extractedBlocks = blocks.map((entry) =>
      classify(entry.element, entry.texts.join(" ").replace(/\s+/g, " ").trim())
    );
    const unsupportedElements = unsupportedSelectors
      .map((item) => ({
        type: item.type,
        count: root.querySelectorAll(item.selector).length
      }))
      .filter((item) => item.count > 0);
    const title =
      document.querySelector("h1")?.textContent?.trim() ||
      document.title.replace(/ - 飞书$/, "").trim() ||
      "未命名文档";

    return {
      title,
      currentUrl: location.href,
      plainText: root.innerText?.replace(/\n{3,}/g, "\n\n").trim() || "",
      rootSelector: rootSelectors.find((selector) => root.matches?.(selector)) || "body",
      unsupportedElements,
      blocks: extractedBlocks
    };
  });

  const blocks = postProcessBlocks(raw.blocks);
  const stats = {
    blockCount: blocks.length,
    headingCount: blocks.filter((block) => block.type === "heading").length,
    paragraphCount: blocks.filter((block) => block.type === "paragraph").length,
    listCount: blocks.filter((block) => block.type === "list_item").length
  };

  return {
    ...raw,
    blocks,
    stats
  };
}
