<!-- BarChartAnimated.svelte -->
<script lang="ts">
  export let size: number = 24;
  export let speed: number = 400;
  export let active: boolean = false;

  $: step = Math.max(0, Math.round(speed * 0.2));
</script>

<svg
  class={`bar-chart-anim ${active ? 'is-active' : ''}`}
  style={`--speed:${speed}ms; --step:${step}ms;`}
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-label="Bar chart"
>
  <line class="bar b1" x1="12" y1="20" x2="12" y2="10" />
  <line class="bar b2" x1="18" y1="20" x2="18" y2="4" />
  <line class="bar b3" x1="6"  y1="20" x2="6"  y2="14" />
</svg>

<style>
  .bar-chart-anim .bar {
    transform-box: fill-box;
    transform-origin: center bottom;
    will-change: transform;
  }

  .bar-chart-anim:is(:hover, .is-active) .bar {
    animation-name: barGrow;
    animation-duration: var(--speed);
    animation-timing-function: cubic-bezier(.2,.9,.2,1);
    animation-iteration-count: 1;
    animation-fill-mode: both;
  }

  .bar-chart-anim:is(:hover, .is-active) .b1 { animation-delay: 0ms; }
  .bar-chart-anim:is(:hover, .is-active) .b2 { animation-delay: var(--step); }
  .bar-chart-anim:is(:hover, .is-active) .b3 { animation-delay: calc(var(--step) * 2); }

  @keyframes barGrow {
    0%   { transform: scaleY(1); }
    30%  { transform: scaleY(0.4); }
    70%  { transform: scaleY(1.1); }
    100% { transform: scaleY(1); }
  }

  @media (prefers-reduced-motion: reduce) {
    .bar-chart-anim:is(:hover, .is-active) .bar { animation: none; }
  }
</style>
