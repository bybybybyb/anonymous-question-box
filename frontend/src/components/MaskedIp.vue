<template>
  <span
    tabindex="0"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
    @focus="focused = true"
    @blur="focused = false"
  >{{ hovered || focused ? ip : "******" }}</span>
</template>

<script>
export default {
  name: "MaskedIp",
  props: {
    ip: { type: String, required: true },
  },
  data() {
    return { hovered: false, focused: false };
  },
};
</script>
