<script setup lang="ts">
// Steps as stops on the route (docs/website-redesign/02 §3): down on phones, across on wide screens; the last stop
// is where you arrive, with the brand's yellow dot. Used by the home page and the drivers page.
defineProps<{ items: { key: string, title?: string, body: string }[] }>()
</script>

<template>
  <ol
    class="stops"
    :style="{ '--count': items.length }"
  >
    <li
      v-for="(item, index) in items"
      :key="item.key"
      :class="{ last: index === items.length - 1 }"
    >
      <span
        class="stop"
        aria-hidden="true"
      />
      <h3 v-if="item.title">
        {{ item.title }}
      </h3>
      <p :class="{ alone: !item.title }">
        {{ item.body }}
      </p>
    </li>
  </ol>
</template>

<style scoped>
.stops {
  --stop: 28px;

  display: grid;
  gap: var(--space-6);
  margin: 0;
  padding: 0;
  list-style: none;
}

.stops li {
  position: relative;
  padding-left: calc(var(--stop) + var(--space-4));
}

/* The route between stops. */
.stops li:not(.last)::after {
  content: '';
  position: absolute;
  top: calc(var(--stop) / 2);
  bottom: calc(-1 * var(--space-6) - var(--stop) / 2);
  left: calc(var(--stop) / 2 - 3px);
  width: 6px;
  background: var(--primary);
}

.stop {
  position: absolute;
  z-index: 1;
  top: 0;
  left: 0;
  width: var(--stop);
  height: var(--stop);
  border-radius: 50%;
  background: var(--bg);
  box-shadow: inset 0 0 0 6px var(--primary);
}

/* Arrival: the green stop with the brand's yellow dot inside. */
.last .stop {
  background: var(--accent);
  box-shadow: inset 0 0 0 7px var(--primary);
}

h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-h3);
  line-height: var(--stop);
}

p {
  margin: 0;
  color: var(--muted);
}

/* A step without a title is a single sentence, read at body size next to its stop. */
p.alone {
  min-height: var(--stop);
  color: var(--text);
  font-weight: 600;
  line-height: 1.45;
  padding-top: 2px;
}

@media (min-width: 720px) {
  .stops {
    grid-template-columns: repeat(var(--count), 1fr);
  }

  .stops li {
    padding: calc(var(--stop) + var(--space-4)) var(--space-4) 0 0;
  }

  .stops li:not(.last)::after {
    top: calc(var(--stop) / 2 - 3px);
    bottom: auto;
    left: var(--stop);
    right: calc(-1 * var(--space-6));
    width: auto;
    height: 6px;
  }

  p.alone {
    padding-top: 0;
  }
}
</style>
