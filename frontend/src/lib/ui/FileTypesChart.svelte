<script>
	let {
		files = {},
		totalFiles = 0,
	} = $props();

	// GitHub Linguist-style colors + SVG icon ids
	const EXT_META = {
		'.py':      { color: '#3572A5', name: 'Python',      icon: 'python' },
		'.js':      { color: '#F7DF1E', name: 'JavaScript',  icon: 'js' },
		'.ts':      { color: '#3178C6', name: 'TypeScript',  icon: 'ts' },
		'.jsx':     { color: '#61DAFB', name: 'React JSX',   icon: 'react' },
		'.tsx':     { color: '#3178C6', name: 'React TSX',   icon: 'react' },
		'.svelte':  { color: '#FF3E00', name: 'Svelte',      icon: 'svelte' },
		'.vue':     { color: '#42B883', name: 'Vue',         icon: 'vue' },
		'.css':     { color: '#563D7C', name: 'CSS',         icon: 'css' },
		'.scss':    { color: '#CF649A', name: 'SCSS',        icon: 'css' },
		'.html':    { color: '#E34F26', name: 'HTML',        icon: 'html' },
		'.json':    { color: '#A0A0A0', name: 'JSON',        icon: 'json' },
		'.yaml':    { color: '#CB171E', name: 'YAML',        icon: 'yaml' },
		'.yml':     { color: '#CB171E', name: 'YAML',        icon: 'yaml' },
		'.md':      { color: '#519ABA', name: 'Markdown',    icon: 'md' },
		'.go':      { color: '#00ADD8', name: 'Go',          icon: 'go' },
		'.rs':      { color: '#DEA584', name: 'Rust',        icon: 'rust' },
		'.java':    { color: '#B07219', name: 'Java',        icon: 'java' },
		'.rb':      { color: '#CC342D', name: 'Ruby',        icon: 'ruby' },
		'.php':     { color: '#4F5D95', name: 'PHP',         icon: 'php' },
		'.sh':      { color: '#89E051', name: 'Shell',       icon: 'shell' },
		'.bat':     { color: '#C1F12E', name: 'Batch',       icon: 'shell' },
		'.sql':     { color: '#E38C00', name: 'SQL',         icon: 'sql' },
		'.toml':    { color: '#9C4121', name: 'TOML',        icon: 'cfg' },
		'.cfg':     { color: '#7B7B7B', name: 'Config',      icon: 'cfg' },
		'.txt':     { color: '#6E6E6E', name: 'Text',        icon: 'txt' },
		'.svg':     { color: '#FFB13B', name: 'SVG',         icon: 'svg' },
		'.png':     { color: '#5A9E6F', name: 'PNG',         icon: 'img' },
		'.jpg':     { color: '#5A9E6F', name: 'JPEG',        icon: 'img' },
		'.lock':    { color: '#555555', name: 'Lock',        icon: 'lock' },
		'.c':       { color: '#555555', name: 'C',           icon: 'c' },
		'.cpp':     { color: '#F34B7D', name: 'C++',         icon: 'cpp' },
		'.cs':      { color: '#178600', name: 'C#',          icon: 'csharp' },
		'.swift':   { color: '#F05138', name: 'Swift',       icon: 'swift' },
		'.kt':      { color: '#A97BFF', name: 'Kotlin',      icon: 'kotlin' },
		'.dart':    { color: '#00B4AB', name: 'Dart',        icon: 'dart' },
	};

	const OTHER_COLOR = '#555';

	function getMeta(ext) {
		return EXT_META[ext.toLowerCase()] || {
			color: OTHER_COLOR,
			name: ext,
			icon: 'generic',
		};
	}

	// Prepare slices: sorted desc, group <2% into "Other"
	let slices = $derived.by(() => {
		const entries = Object.entries(files || {}).sort((a, b) => b[1] - a[1]);
		const total = totalFiles || entries.reduce((s, e) => s + e[1], 0) || 1;
		const threshold = total * 0.02;

		const main = [];
		let otherCount = 0;

		for (const [ext, count] of entries) {
			if (count >= threshold && main.length < 12) {
				const meta = getMeta(ext);
				main.push({ ext, count, pct: (count / total * 100), ...meta });
			} else {
				otherCount += count;
			}
		}

		if (otherCount > 0) {
			main.push({
				ext: 'other', count: otherCount, pct: (otherCount / total * 100),
				color: OTHER_COLOR, name: 'Other', icon: 'other',
			});
		}

		return main;
	});

	// SVG donut arc paths
	const CX = 100, CY = 100, R = 80, STROKE = 28;

	function arcPaths(items) {
		const total = items.reduce((s, i) => s + i.count, 0) || 1;
		const paths = [];
		let angle = -90;
		const GAP = items.length > 1 ? 1.5 : 0;

		for (const item of items) {
			const sweep = (item.count / total) * 360 - GAP;
			if (sweep <= 0) continue;

			const startRad = (angle * Math.PI) / 180;
			const endRad = ((angle + sweep) * Math.PI) / 180;

			const x1 = CX + R * Math.cos(startRad);
			const y1 = CY + R * Math.sin(startRad);
			const x2 = CX + R * Math.cos(endRad);
			const y2 = CY + R * Math.sin(endRad);

			const large = sweep > 180 ? 1 : 0;

			paths.push({
				...item,
				d: `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2}`,
			});

			angle += sweep + GAP;
		}
		return paths;
	}

	let arcs = $derived(arcPaths(slices));
	let hovered = $state(null);

	function txtCol(hex) {
		if (!hex || hex.length < 7) return '#fff';
		const r = parseInt(hex.slice(1, 3), 16);
		const g = parseInt(hex.slice(3, 5), 16);
		const b = parseInt(hex.slice(5, 7), 16);
		return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 ? '#111' : '#fff';
	}
</script>

<div class="chart-wrap">
	<!-- Donut -->
	<div class="donut-box">
		<svg viewBox="0 0 200 200" class="donut-svg">
			<circle cx={CX} cy={CY} r={R} fill="none" stroke="var(--bd)" stroke-width={STROKE} opacity="0.25" />

			{#each arcs as arc, i}
				<path
					d={arc.d}
					fill="none"
					stroke={arc.color}
					stroke-width={hovered === i ? STROKE + 6 : STROKE}
					stroke-linecap="butt"
					opacity={hovered !== null && hovered !== i ? 0.3 : 1}
					style="transition: all .15s ease; cursor: pointer;"
					role="img"
					aria-label={arc.name}
					onmouseenter={() => hovered = i}
					onmouseleave={() => hovered = null}
				/>
			{/each}

			<text x={CX} y={CY - 8} text-anchor="middle" dominant-baseline="central" class="c-num">{totalFiles}</text>
			<text x={CX} y={CY + 14} text-anchor="middle" dominant-baseline="central" class="c-lbl">files</text>
		</svg>

		{#if hovered !== null && arcs[hovered]}
			<div class="tip">
				<span class="tip-dot" style="background:{arcs[hovered].color}"></span>
				<b>{arcs[hovered].name}</b>
				<span class="tip-v">{arcs[hovered].count} ({arcs[hovered].pct.toFixed(1)}%)</span>
			</div>
		{/if}
	</div>

	<!-- Legend -->
	<div class="legend">
		{#each slices as item, i}
			<button
				type="button"
				class="leg-row"
				class:dimmed={hovered !== null && hovered !== i}
				onmouseenter={() => hovered = i}
				onmouseleave={() => hovered = null}
			>
				<span class="badge" style="background:{item.color}">
					<svg viewBox="0 0 24 24" width="15" height="15" fill="none" xmlns="http://www.w3.org/2000/svg">
						{@html iconSvg(item.icon, txtCol(item.color))}
					</svg>
				</span>
				<span class="leg-name">{item.name}</span>
				<span class="leg-cnt">{item.count}</span>
				<span class="bar-t">
						<span class="bar-f" style="width:{item.pct}%; background:{item.color}"></span>
						<span class="bar-val">{item.pct.toFixed(1)}%</span>
					</span>
			</button>
		{/each}
	</div>
</div>

<script module>
	/**
	 * Returns raw SVG inner markup for a given file-type icon.
	 * Each icon is a mini illustration inside a 24×24 viewBox.
	 */
	function iconSvg(id, c) {
		const icons = {
			python:
				`<path d="M11.8 2.4c-3.6 0-3.4 1.6-3.4 1.6v1.6h3.5v.5H6.3S3.2 5.8 3.2 9.5s2.7 3.5 2.7 3.5h1.6v-1.7s-.1-2.7 2.6-2.7h3.5s2.5 0 2.5-2.4V4.1s.4-1.7-4.3-1.7zm-2.3 1c.4 0 .8.3.8.8s-.4.8-.8.8-.8-.3-.8-.8.4-.8.8-.8z" fill="${c}"/>` +
				`<path d="M12.2 21.6c3.6 0 3.4-1.6 3.4-1.6v-1.6h-3.5v-.5h5.6s3.1.3 3.1-3.4-2.7-3.5-2.7-3.5h-1.6v1.7s.1 2.7-2.6 2.7H10.4s-2.5 0-2.5 2.4v2.1s-.4 1.7 4.3 1.7zm2.3-1c-.4 0-.8-.3-.8-.8s.4-.8.8-.8.8.3.8.8-.4.8-.8.8z" fill="${c}"/>`,
			js:
				`<rect x="3" y="3" width="18" height="18" rx="2" fill="${c}" opacity=".18"/>` +
				`<text x="12" y="17" text-anchor="middle" font-size="11" font-weight="900" font-family="system-ui" fill="${c}">JS</text>`,
			ts:
				`<rect x="3" y="3" width="18" height="18" rx="2" fill="${c}" opacity=".18"/>` +
				`<text x="12" y="17" text-anchor="middle" font-size="11" font-weight="900" font-family="system-ui" fill="${c}">TS</text>`,
			react:
				`<ellipse cx="12" cy="12" rx="10" ry="4" stroke="${c}" stroke-width="1.2"/>` +
				`<ellipse cx="12" cy="12" rx="10" ry="4" stroke="${c}" stroke-width="1.2" transform="rotate(60 12 12)"/>` +
				`<ellipse cx="12" cy="12" rx="10" ry="4" stroke="${c}" stroke-width="1.2" transform="rotate(120 12 12)"/>` +
				`<circle cx="12" cy="12" r="2" fill="${c}"/>`,
			svelte:
				`<path d="M17.6 5.2C15.7 2.7 12.2 2.1 9.9 3.9 7.5 5.6 6.9 8.8 8.4 11l.1.1c-1.4 2-1 5 1.4 6.6 2.4 1.7 5.6 1.1 7.3-1.2.6-.9 1-2 .9-3-.1-1.6-1-3-2.4-3.8l-.1-.1c1.4-2 .8-5-1.4-6.6z" fill="${c}" opacity=".9"/>` +
				`<path d="M10.3 15.8c-.8.3-1.8-.2-2-1.1-.1-.3-.1-.6 0-.9l.3-.8 1.3.9c.2.2.4.4.4.7 0 .5-.2 1.1-.7 1.2z" fill="none"/>`,
			vue:
				`<path d="M2 3h4l6 10.5L18 3h4L12 21z" fill="${c}" opacity=".5"/>` +
				`<path d="M7 3h3l2 3.5L14 3h3L12 14z" fill="${c}"/>`,
			css:
				`<path d="M4 2l1.5 17L12 22l6.5-3L20 2z" fill="${c}" opacity=".18"/>` +
				`<text x="12" y="16" text-anchor="middle" font-size="9" font-weight="900" font-family="system-ui" fill="${c}">CSS</text>`,
			html:
				`<path d="M4 2l1.5 17L12 22l6.5-3L20 2z" fill="${c}" opacity=".18"/>` +
				`<text x="12" y="15.5" text-anchor="middle" font-size="7.5" font-weight="900" font-family="system-ui" fill="${c}">&lt;/&gt;</text>`,
			json:
				`<text x="12" y="17" text-anchor="middle" font-size="15" font-weight="300" font-family="monospace" fill="${c}">{ }</text>`,
			yaml:
				`<text x="12" y="16" text-anchor="middle" font-size="8.5" font-weight="800" font-family="system-ui" fill="${c}">YML</text>`,
			md:
				`<rect x="2" y="5" width="20" height="14" rx="2" stroke="${c}" stroke-width="1.5" fill="none"/>` +
				`<path d="M5.5 15V9l2.5 3.5L10.5 9v6M17 15l-2.5-3M17 9v6M14.5 12H17" stroke="${c}" stroke-width="1.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
			go:
				`<text x="12" y="17" text-anchor="middle" font-size="13" font-weight="900" font-family="system-ui" fill="${c}">Go</text>`,
			rust:
				`<circle cx="12" cy="12" r="5.5" stroke="${c}" stroke-width="1.8" fill="none"/>` +
				`<text x="12" y="15.5" text-anchor="middle" font-size="8" font-weight="900" font-family="system-ui" fill="${c}">R</text>` +
				[0,60,120,180,240,300].map(d =>
					`<line x1="${12+8.5*Math.cos(d*Math.PI/180)}" y1="${12+8.5*Math.sin(d*Math.PI/180)}" x2="${12+6.5*Math.cos(d*Math.PI/180)}" y2="${12+6.5*Math.sin(d*Math.PI/180)}" stroke="${c}" stroke-width="2" stroke-linecap="round"/>`
				).join(''),
			java:
				`<path d="M6 8h9v5.5c0 1.8-2 3.5-4.5 3.5S6 15.3 6 13.5z" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<path d="M15 10c1.5 0 2.5.8 2.5 2s-1 2-2.5 2" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<path d="M8.5 6.5c0-1 .5-1.8 1.2-1.8M11.5 6.5c0-1.2.5-2 1.2-2" stroke="${c}" stroke-width=".9" fill="none" stroke-linecap="round"/>`,
			ruby:
				`<polygon points="12,3 20,10 12,21 4,10" stroke="${c}" stroke-width="1.3" fill="${c}" fill-opacity=".15"/>` +
				`<polyline points="4,10 12,13 20,10" stroke="${c}" stroke-width="1" fill="none"/>` +
				`<line x1="12" y1="3" x2="12" y2="21" stroke="${c}" stroke-width="1"/>`,
			php:
				`<ellipse cx="12" cy="12" rx="10" ry="7" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<text x="12" y="15.5" text-anchor="middle" font-size="8" font-weight="900" font-family="system-ui" fill="${c}">php</text>`,
			shell:
				`<rect x="2" y="4" width="20" height="16" rx="2.5" stroke="${c}" stroke-width="1.5" fill="none"/>` +
				`<polyline points="6,10 9.5,13 6,16" stroke="${c}" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>` +
				`<line x1="12" y1="16" x2="18" y2="16" stroke="${c}" stroke-width="1.6" stroke-linecap="round"/>`,
			sql:
				`<ellipse cx="12" cy="7" rx="7" ry="3" stroke="${c}" stroke-width="1.4" fill="none"/>` +
				`<path d="M5 7v10c0 1.7 3.1 3 7 3s7-1.3 7-3V7" stroke="${c}" stroke-width="1.4" fill="none"/>` +
				`<path d="M5 12.5c0 1.7 3.1 3 7 3s7-1.3 7-3" stroke="${c}" stroke-width=".8" fill="none" opacity=".5"/>`,
			cfg:
				`<circle cx="12" cy="12" r="3" stroke="${c}" stroke-width="1.5" fill="none"/>` +
				`<path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1l2.1-2.1M17 7l2.1-2.1" stroke="${c}" stroke-width="1.5" stroke-linecap="round"/>`,
			txt:
				`<line x1="4" y1="6" x2="20" y2="6" stroke="${c}" stroke-width="1.5" stroke-linecap="round"/>` +
				`<line x1="4" y1="10" x2="16" y2="10" stroke="${c}" stroke-width="1.5" stroke-linecap="round"/>` +
				`<line x1="4" y1="14" x2="18" y2="14" stroke="${c}" stroke-width="1.5" stroke-linecap="round"/>` +
				`<line x1="4" y1="18" x2="12" y2="18" stroke="${c}" stroke-width="1.5" stroke-linecap="round"/>`,
			img:
				`<rect x="3" y="5" width="18" height="14" rx="2" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<circle cx="8" cy="10" r="1.8" fill="${c}"/>` +
				`<polyline points="3,17 8,13 11,15 15,10 21,17" stroke="${c}" stroke-width="1.3" fill="none" stroke-linejoin="round"/>`,
			lock:
				`<rect x="6" y="11" width="12" height="9" rx="2" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<circle cx="12" cy="15.5" r="1.3" fill="${c}"/>`,
			svg:
				`<text x="12" y="16" text-anchor="middle" font-size="8.5" font-weight="800" font-family="system-ui" fill="${c}">SVG</text>`,
			c:
				`<text x="12" y="17" text-anchor="middle" font-size="14" font-weight="900" font-family="system-ui" fill="${c}">C</text>`,
			cpp:
				`<text x="12" y="16.5" text-anchor="middle" font-size="10" font-weight="900" font-family="system-ui" fill="${c}">C++</text>`,
			csharp:
				`<text x="12" y="16.5" text-anchor="middle" font-size="11" font-weight="900" font-family="system-ui" fill="${c}">C#</text>`,
			swift:
				`<path d="M18 4c-4.5 3.5-8.5 5.5-11.5 6 2.5-.8 5.5-3 8-5.5-2.5 3-6 5.5-10 7 2.5.5 6-.3 9.5-3-2 2.5-5 4.2-8 4.7 2 1.2 5.8.4 9.5-2-1 1.7-3 3.4-6 4.3 3.8 0 7-1.7 8.7-4.5.8-1.3.4-4.2-.7-6z" fill="${c}"/>`,
			kotlin:
				`<polygon points="3,3 21,3 12,12 21,21 3,21" fill="${c}" opacity=".7"/>`,
			dart:
				`<path d="M4 12l3-9h10l4 4v10l-9 3z" stroke="${c}" stroke-width="1.3" fill="${c}" fill-opacity=".15"/>`,
			other:
				`<circle cx="6" cy="12" r="2" fill="${c}"/><circle cx="12" cy="12" r="2" fill="${c}"/><circle cx="18" cy="12" r="2" fill="${c}"/>`,
			generic:
				`<path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" stroke="${c}" stroke-width="1.3" fill="none"/>` +
				`<polyline points="14,2 14,8 20,8" stroke="${c}" stroke-width="1.3" fill="none"/>`,
		};
		return icons[id] || icons.generic;
	}
</script>

<style>
	.chart-wrap { display: flex; align-items: flex-start; gap: 1.75rem; }

	.donut-box { position: relative; flex-shrink: 0; width: 16rem; height: 16rem; }
	.donut-svg { width: 100%; height: 100%; overflow: visible; }

	.c-num { font-size: 1.625rem; font-weight: 800; fill: var(--tx-bright); font-family: var(--font-ui); }
	.c-lbl { font-size: 0.6875rem; fill: var(--tx-dim); text-transform: uppercase; letter-spacing: 0.0625rem; font-family: var(--font-ui); }

	.tip {
		position: absolute; bottom: -1.75rem; left: 50%; transform: translateX(-50%);
		background: var(--sf); border: 0.0625rem solid var(--bd); border-radius: 0.375rem;
		padding: 0.25rem 0.625rem; display: flex; align-items: center; gap: 0.375rem;
		font-size: 0.75rem; white-space: nowrap; pointer-events: none; font-family: var(--font-ui);
	}
	.tip-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; flex-shrink: 0; }
	.tip b { color: var(--tx-bright); font-weight: 600; }
	.tip-v { color: var(--tx-dim); }

	.legend { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.125rem; }

	.leg-row {
		display: grid; grid-template-columns: 2.125rem 1fr auto 4.5rem;
		align-items: center; gap: 0.5rem; padding: 0.3125rem 0.5rem; border-radius: 0.25rem;
		transition: opacity .12s, background .12s; cursor: pointer;
		background: none; border: none; color: inherit; font: inherit; text-align: left; width: 100%;
	}
	.leg-row:hover { background: rgba(255,255,255,.04); }
	.leg-row.dimmed { opacity: 0.3; }

	.badge {
		display: inline-flex; align-items: center; justify-content: center;
		width: 2.125rem; height: 1.375rem; border-radius: 0.3125rem; flex-shrink: 0; overflow: hidden;
	}
	.badge svg { flex-shrink: 0; }

	.leg-name { font-size: 0.8125rem; color: var(--tx-bright); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.leg-cnt  { font-size: 0.8125rem; font-family: var(--font-ui); color: var(--tx); text-align: right; }

	.bar-t { width: 4.5rem; height: 0.875rem; background: var(--bd); border-radius: 0.25rem; overflow: hidden; position: relative; }
	.bar-f { height: 100%; border-radius: 0.25rem; transition: width .3s ease; }
	.bar-val {
		position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
		font-size: 0.5625rem; font-family: var(--font-ui); color: var(--tx-bright);
		letter-spacing: 0.01rem; pointer-events: none;
	}
</style>
