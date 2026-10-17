<script setup lang="ts">
// The frame of the one-task pages a link from an email or the app opens (verify the email, a new password, an
// invitation that does not exist): the wordmark and one card, centered, nothing else to read.
</script>

<template>
  <section class="utility">
    <div class="box">
      <div class="card">
        <KuulisWordmark
          :size="28"
          class="mark"
        />
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.utility {
  padding: clamp(40px, 8vw, 112px) var(--gutter) var(--section-y);
}

.box {
  max-width: 480px;
  margin: 0 auto;
}

.card {
  padding: clamp(24px, 5vw, 40px);
}

.mark {
  display: block;
  margin-bottom: var(--space-6);
  color: var(--primary);
}

.card :deep(h1) {
  margin: 0 0 var(--space-3);
  font-size: var(--font-h2);
  line-height: var(--leading-heading);
  letter-spacing: var(--tracking-heading);
}

.card :deep(h1 + p) {
  margin-top: 0;
}

.card :deep(.wide) {
  width: 100%;
  margin-top: var(--space-2);
}
</style>
