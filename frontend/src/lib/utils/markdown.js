/**
 * Markdown → HTML renderer powered by markdown-it + highlight.js.
 *
 * Replaces the previous hand-rolled regex renderer with a standards-compliant
 * CommonMark parser.  All strip/pre-processing helpers now operate on the
 * markdown-it token stream instead of custom state-machine logic.
 *
 * @module utils/markdown
 */

import markdownit from 'markdown-it';
import hljs from 'highlight.js/lib/common';

// ─── markdown-it instance (singleton) ────────────────────────────────

const md = markdownit({
	html: false,     // no raw HTML pass-through (safe for LLM output)
	linkify: false,  // don't auto-convert plain URLs
	typographer: false,
});

// ─── Highlight.js integration ────────────────────────────────────────

const defaultFenceRender =
	md.renderer.rules.fence ||
	function (tokens, idx, options, _env, self) {
		return self.renderToken(tokens, idx, options);
	};

md.renderer.rules.fence = function (tokens, idx, options, env, self) {
	const token = tokens[idx];
	const lang = token.info ? token.info.trim().split(/\s+/)[0] : '';

	if (lang && hljs.getLanguage(lang)) {
		try {
			const highlighted = hljs.highlight(token.content, {
				language: lang,
				ignoreIllegals: true,
			}).value;

			const langAttr = md.utils.escapeHtml(lang);
			return (
				`<pre><code class="hljs language-${langAttr}">` +
				highlighted +
				'</code></pre>\n'
			);
		} catch {
			/* fall through to default */
		}
	}

	return defaultFenceRender(tokens, idx, options, env, self);
};

// ─── Checkbox plugin (inline, no external dependency) ────────────────

function checkboxPlugin(mdInstance) {
	mdInstance.core.ruler.after('inline', 'checkbox', function (state) {
		for (const token of state.tokens) {
			if (token.type !== 'inline' || !token.children?.length) continue;
			const first = token.children[0];
			if (first.type !== 'text') continue;
			const c = first.content;
			if (/^\[x\]\s/i.test(c)) {
				first.content = '☑ ' + c.slice(4);
			} else if (c.startsWith('[ ] ')) {
				first.content = '☐ ' + c.slice(4);
			}
		}
	});
}
md.use(checkboxPlugin);

// ─── Links open in new tab ───────────────────────────────────────────

const defaultLinkOpen =
	md.renderer.rules.link_open ||
	function (tokens, idx, options, _env, self) {
		return self.renderToken(tokens, idx, options);
	};

md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
	tokens[idx].attrSet('target', '_blank');
	tokens[idx].attrSet('rel', 'noopener noreferrer');
	return defaultLinkOpen(tokens, idx, options, env, self);
};

// ─── Public API ──────────────────────────────────────────────────────

/**
 * Render markdown text to sanitised HTML.
 *
 * Automatically strips a single outer ```markdown wrapper that LLMs
 * sometimes add around the entire response.
 *
 * @param {string} text
 * @returns {string}
 */
export function renderMarkdown(text) {
	if (!text) return '';
	let src = stripOuterMarkdownFence(text);
	src = unwrapMarkdownFences(src);
	return md.render(src);
}

/**
 * Strip all top-level fenced code blocks from text, returning only the
 * non-code parts.  Uses the markdown-it token stream so it handles any
 * valid CommonMark fence (variable backtick counts, info-strings, etc.).
 *
 * @param {string} text
 * @returns {string}
 */
export function stripFencedBlocks(text) {
	return _stripByToken(text, () => true);
}

/**
 * Strip only file-path code blocks from text, preserving all others.
 *
 * File blocks are identified by an info-string containing `/` or `.`
 * (e.g. ```src/app.py), matching the backend `_parse_file_blocks`
 * heuristic.  These blocks are shown as interactive file cards in the UI,
 * so they must be removed from the markdown to avoid duplication.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripFilePathBlocks(text) {
	return _stripByToken(text, (info) => {
		return info.includes('/') || info.includes('.');
	});
}

/**
 * HTML-escape a string.
 *
 * @deprecated Prefer markdown-it's built-in escaping via md.utils.escapeHtml.
 *             Kept for backward compatibility.
 * @param {string} s
 * @returns {string}
 */
export function esc(s) {
	return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Parse clarifications.md into structured Q&A blocks.
 * @param {string} text
 * @returns {{ num: number, question: string, answer: string }[]}
 */
export function parseClarifications(text) {
	const blocks = [];
	const parts = text.split(/^## Question\s+(\d+)\s*$/m);
	for (let i = 1; i < parts.length - 1; i += 2) {
		const num = parseInt(parts[i], 10);
		const block = parts[i + 1];

		// Split off answer
		const answerSplit = block.split(/^\*\*Answer:\*\*\s*$/m);
		const beforeAnswer = answerSplit[0] || '';
		const answer = (answerSplit[1] || '').trim();

		// Extract context
		const ctxMatch = beforeAnswer.match(/^\*Context:\*\s*(.+)$/m);
		const context = ctxMatch ? ctxMatch[1].trim() : '';

		// Extract options
		const options = [];
		const optsSplit = beforeAnswer.split(/^\*\*Options:\*\*\s*$/m);
		if (optsSplit.length > 1) {
			const optBlock = optsSplit[1];
			for (const m of optBlock.matchAll(/^- [A-Z]\)\s*(.+)$/gm)) {
				options.push(m[1].trim());
			}
		}

		// Question text: remove context + options markers
		let question = beforeAnswer
			.replace(/^\*Context:\*\s*.+$/m, '')
			.replace(/^\*\*Options:\*\*[\s\S]*$/m, '')
			.trim();

		blocks.push({ num, question, context, options, answer });
	}
	return blocks;
}

/**
 * Parse clarify questions from LLM response text.
 * @param {string} text
 * @returns {string[]}
 */
export function parseClarifyQuestions(text) {
	const questions = [];
	const lines = text.split('\n');
	let current = [];
	let inQuestion = false;
	const re = /^(\*{0,2}\s*(?:Question\s+|Q)\d+[\s:.)\\*]|(?:\*{2})?\d+[\s:.)\\*])/i;

	for (const line of lines) {
		if (re.test(line.trim())) {
			if (current.length > 0 && inQuestion) {
				questions.push(current.join('\n').trim());
			}
			current = [line];
			inQuestion = true;
		} else if (inQuestion) {
			current.push(line);
		}
	}
	if (current.length > 0 && inQuestion) {
		questions.push(current.join('\n').trim());
	}
	return questions;
}

/**
 * Strip `--- FILE: path ---` … `--- END FILE ---` marker blocks from text.
 *
 * These markers are used by the LLM output format so the backend can parse
 * proposed file contents.  They must not be rendered in the chat UI because
 * file cards handle that display.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripFileMarkers(text) {
	if (!text) return '';
	const lines = text.split('\n');
	const result = [];
	let inside = false;

	for (const line of lines) {
		const stripped = line.trim();
		if (!inside && stripped.startsWith('--- FILE:') && stripped.endsWith('---')) {
			inside = true;
			continue;
		}
		if (inside && stripped === '--- END FILE ---') {
			inside = false;
			continue;
		}
		if (!inside) {
			result.push(line);
		}
	}
	return result.join('\n');
}

// ─── Internal helpers ────────────────────────────────────────────────

/**
 * Generic token-based fence stripper.
 *
 * Parses `text` with markdown-it, finds all `fence` tokens whose
 * info-string satisfies `shouldStrip(info)`, and removes the
 * corresponding source lines.
 *
 * @param {string} text
 * @param {(info: string) => boolean} shouldStrip
 * @returns {string}
 */
function _stripByToken(text, shouldStrip) {
	if (!text) return '';

	const tokens = md.parse(text, {});
	const lines = text.split('\n');

	// Collect [start, end) line ranges to exclude (already sorted by position)
	const excludes = [];
	for (const token of tokens) {
		if (token.type === 'fence' && token.map) {
			const info = (token.info || '').trim();
			if (shouldStrip(info)) {
				excludes.push(token.map);
			}
		}
	}

	if (excludes.length === 0) return text;

	const result = [];
	let cursor = 0;
	for (const [start, end] of excludes) {
		for (; cursor < start; cursor++) result.push(lines[cursor]);
		cursor = end;
	}
	for (; cursor < lines.length; cursor++) result.push(lines[cursor]);

	return result.join('\n');
}

/**
 * Strip a single outer ```markdown / ```md / bare ``` wrapper that LLMs
 * sometimes place around the entire response.
 *
 * Uses the markdown-it token stream: if the entire text parses as a
 * single `fence` token whose info-string is "markdown", "md", or empty
 * (allowing leading/trailing blank lines), return the fence content.
 *
 * @param {string} text
 * @returns {string}
 */
function stripOuterMarkdownFence(text) {
	const tokens = md.parse(text, {});
	const fences = tokens.filter((t) => t.type === 'fence');

	if (fences.length !== 1) return text;

	const ft = fences[0];
	const info = (ft.info || '').trim().toLowerCase();
	if (info !== 'markdown' && info !== 'md' && info !== '') return text;

	// Verify the fence spans the full text (ignoring blank surrounding lines)
	if (!ft.map) return text;
	const [start, end] = ft.map;
	const lines = text.split('\n');

	for (let i = 0; i < start; i++) {
		if (lines[i].trim()) return text;
	}
	for (let i = end; i < lines.length; i++) {
		if (lines[i].trim()) return text;
	}

	return ft.content;
}

/**
 * Unwrap top-level ```markdown / ```md fences whose content is plain
 * markdown and should be rendered normally — not displayed as code.
 *
 * Unlike stripOuterMarkdownFence (which only handles a single fence
 * spanning the entire document), this handles documents where the LLM
 * placed markdown content inside a ```markdown fence alongside other
 * blocks (e.g. a ```yaml verify section).
 *
 * @param {string} text
 * @returns {string}
 */
function unwrapMarkdownFences(text) {
	if (!text) return '';

	const tokens = md.parse(text, {});
	const lines = text.split('\n');

	// Collect fence ranges to unwrap (in reverse order to preserve indices)
	const replacements = [];
	for (const token of tokens) {
		if (token.type !== 'fence' || !token.map) continue;
		const info = (token.info || '').trim().toLowerCase();
		if (info !== 'markdown' && info !== 'md') continue;
		replacements.push({
			start: token.map[0],
			end: token.map[1],
			content: token.content,
		});
	}

	if (replacements.length === 0) return text;

	// Apply replacements in reverse to keep line numbers stable
	const result = [...lines];
	for (let i = replacements.length - 1; i >= 0; i--) {
		const r = replacements[i];
		const unwrapped = r.content.replace(/\n$/, '').split('\n');
		result.splice(r.start, r.end - r.start, ...unwrapped);
	}

	return result.join('\n');
}
