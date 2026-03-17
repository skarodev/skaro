/**
 * Lightweight markdown → HTML renderer.
 * Handles: headers, bold, italic, code blocks, inline code, lists,
 * blockquotes, tables, checkboxes, HR.
 *
 * Code-block extraction uses a line-by-line state machine instead of regex,
 * which correctly handles nested fences, varying backtick counts, and
 * LLM responses wrapped entirely in ```markdown … ```.
 *
 * @param {string} text
 * @returns {string}
 */
export function renderMarkdown(text) {
	if (!text) return '';

	// ── Phase 0: strip a single outer ```markdown wrapper if present ──
	let src = stripOuterMarkdownFence(text);

	// ── Phase 1: extract fenced code blocks via state machine ──
	const slots = [];

	function slot(html) {
		const id = `\x00SLOT${slots.length}\x00`;
		slots.push(html);
		return id;
	}

	src = extractFencedBlocks(src, (lang, code) =>
		slot(`<pre><code>${esc(code.trimEnd())}</code></pre>`)
	);

	// Inline code (must run after fenced blocks are slotted)
	src = src.replace(/`([^`\n]+)`/g, (_, code) =>
		slot(`<code>${esc(code)}</code>`)
	);

	// ── Phase 2: escape remaining text ──
	let h = esc(src);

	// Headers
	h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
	h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
	h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
	// Bold, italic
	h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
	h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
	// Blockquote
	h = h.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
	// HR
	h = h.replace(/^---$/gm, '<hr>');
	// Checkbox lists (must come before generic list rule)
	h = h.replace(/^- \[x\] (.+)$/gim, '<li>☑ $1</li>');
	h = h.replace(/^- \[ \] (.+)$/gm, '<li>☐ $1</li>');
	// Lists
	h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
	h = h.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
	// Tables
	h = h.replace(/^\|(.+)\|$/gm, (_, row) => {
		const cells = row.split('|').map((c) => c.trim());
		if (cells.every((c) => /^[-:]+$/.test(c))) return '<!--sep-->';
		return '<tr>' + cells.map((c) => `<td>${c}</td>`).join('') + '</tr>';
	});
	h = h.replace(/((?:\s*(?:<tr>.*?<\/tr>|<!--sep-->)\s*)+)/g, (block) => {
		const rows = block.replace(/<!--sep-->/g, '').trim();
		if (!rows) return '';
		const promoted = rows.replace(
			/^<tr>(.*?)<\/tr>/,
			(_, inner) => '<thead><tr>' + inner.replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>') + '</tr></thead>'
		);
		return `<table>${promoted}</table>`;
	});
	// Paragraphs
	h = h.replace(/\n\n/g, '</p><p>');
	h = '<p>' + h + '</p>';
	h = h.replace(/<p>\s*<(h[123]|pre|blockquote|table|hr|li|ul|ol)/g, '<$1');
	h = h.replace(/<\/(h[123]|pre|blockquote|table|hr|li|ul|ol)>\s*<\/p>/g, '</$1>');
	h = h.replace(/<p>\s*<\/p>/g, '');
	// Wrap consecutive <li>
	h = h.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
	h = h.replace(/<\/ul>\s*<ul>/g, '');

	// ── Phase 3: restore slots ──
	for (let i = 0; i < slots.length; i++) {
		h = h.replace(`\x00SLOT${i}\x00`, slots[i]);
	}

	return h;
}

/**
 * Strip a single outer ```markdown / ```md / ``` wrapper that LLMs
 * sometimes place around the entire response.
 *
 * Uses a line-by-line approach (not regex) so it never accidentally
 * matches inner code blocks.
 *
 * @param {string} text
 * @returns {string}
 */
function stripOuterMarkdownFence(text) {
	const lines = text.split('\n');

	// Find the first non-empty line
	let first = -1;
	for (let i = 0; i < lines.length; i++) {
		if (lines[i].trim() !== '') { first = i; break; }
	}
	if (first === -1) return text;

	// Find the last non-empty line
	let last = -1;
	for (let i = lines.length - 1; i >= 0; i--) {
		if (lines[i].trim() !== '') { last = i; break; }
	}
	if (last === -1 || last <= first) return text;

	// Check if first non-empty line is an opening fence
	const openMatch = lines[first].match(/^(`{3,})(?:markdown|md)?\s*$/);
	if (!openMatch) return text;

	const fenceChar = openMatch[1]; // e.g. "```" or "````"
	const minLen = fenceChar.length;

	// Check if last non-empty line is a closing fence with >= same backtick count
	const closeMatch = lines[last].match(/^(`{3,})\s*$/);
	if (!closeMatch || closeMatch[1].length < minLen) return text;

	// Verify there are no unmatched fences in between that would make this
	// NOT a simple outer wrapper. Walk inner lines and track fence depth.
	let depth = 0;
	for (let i = first + 1; i < last; i++) {
		const m = lines[i].match(/^(`{3,})(\S*)\s*$/);
		if (!m) continue;
		if (m[1].length >= minLen) {
			// This could be an inner open or close fence
			depth += (depth > 0 && !m[2]) ? -1 : (m[2] || depth === 0) ? 1 : -1;
		}
	}
	// If depth is 0, all inner fences are balanced → safe to strip
	if (depth !== 0) return text;

	// Strip outer fence
	return lines.slice(first + 1, last).join('\n');
}

/**
 * Extract fenced code blocks from text using a line-by-line state machine.
 *
 * Handles:
 *  - Variable backtick counts (```, ````, etc.)
 *  - Opening fences with or without language tags
 *  - Closing fences with >= opening backtick count
 *  - Proper nesting (outer fence needs more backticks than inner)
 *
 * @param {string} text
 * @param {(lang: string, code: string) => string} replacer
 * @returns {string}
 */
function extractFencedBlocks(text, replacer) {
	const lines = text.split('\n');
	const output = [];

	let inFence = false;
	let fenceLen = 0;
	let fenceLang = '';
	/** @type {string[]} */
	let codeLines = [];

	for (const line of lines) {
		if (!inFence) {
			// Try to match an opening fence: 3+ backticks, optional label, at line start
			const open = line.match(/^(`{3,})(\S*)\s*$/);
			if (open) {
				inFence = true;
				fenceLen = open[1].length;
				fenceLang = open[2] || '';
				codeLines = [];
			} else {
				output.push(line);
			}
		} else {
			// Try to match a closing fence: backticks >= opening count, no other content
			const close = line.match(/^(`{3,})\s*$/);
			if (close && close[1].length >= fenceLen) {
				// End of fenced block
				const code = codeLines.join('\n');
				output.push(replacer(fenceLang, code));
				inFence = false;
				fenceLen = 0;
				fenceLang = '';
				codeLines = [];
			} else {
				codeLines.push(line);
			}
		}
	}

	// If we ended still inside a fence (unclosed), treat remaining lines as code
	if (inFence && codeLines.length > 0) {
		output.push(replacer(fenceLang, codeLines.join('\n')));
	}

	return output.join('\n');
}

/**
 * Strip all top-level fenced code blocks from text, returning only the
 * non-code parts. Uses the same line-by-line state machine as
 * extractFencedBlocks, so it correctly handles nested fences inside
 * JSON/spec content from LLM responses.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripFencedBlocks(text) {
	return extractFencedBlocks(text, () => '');
}

/**
 * Strip only file-path code blocks from text, preserving all others.
 *
 * File blocks are identified by a fence label containing ``/`` or ``.``
 * (e.g. ``\`\`\`src/app.py``), matching the backend ``_parse_file_blocks``
 * heuristic.  These blocks are shown as interactive file cards in the UI,
 * so they must be removed from the markdown text to avoid duplication.
 *
 * All other fenced blocks (language tags like ``python``, ``json``, or
 * bare ``\`\`\```) are kept intact for {@link renderMarkdown} to render
 * as ``<pre><code>`` elements.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripFilePathBlocks(text) {
	return extractFencedBlocks(text, (lang, code) => {
		if (lang && (lang.includes('/') || lang.includes('.'))) {
			return '';
		}
		return `\`\`\`${lang}\n${code}\n\`\`\``;
	});
}

/** @param {string} s */
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
