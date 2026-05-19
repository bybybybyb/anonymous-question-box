<template>
  <main class="live-projector-surface">
    <section v-if="visibleState" class="live-projector-content">
      <div v-if="visibleState.images.length > 0" class="live-projector-images">
        <img
          v-for="(image, index) in visibleState.images"
          :key="imageKey(image, index)"
          :src="imageSrc(image)"
          alt=""
          class="live-projector-image"
        />
      </div>
      <div
        v-if="visibleState.text"
        class="live-projector-text text-start fw-bold"
      >
        <p
          v-for="(sentence, index) in formatText(visibleState.text)"
          :key="index"
          :class="fsClass"
        >
          <strong>{{ sentence }}</strong>
        </p>
      </div>
    </section>
  </main>
</template>

<script>
import {
  DEFAULT_FONT_SIZE_IDX,
  FONT_SIZES,
  readProjectionState,
  subscribeProjectionState,
} from "../liveProjectionState";

function clampFontSizeIdx(fontSizeIdx) {
  if (!Number.isInteger(fontSizeIdx)) {
    return DEFAULT_FONT_SIZE_IDX;
  }
  return Math.min(Math.max(fontSizeIdx, 0), FONT_SIZES.length - 1);
}

export default {
  name: "LiveProjectorView",
  props: {
    owner: String,
  },
  methods: {
    imageKey(image, index) {
      if (typeof image === "string") {
        return image;
      }
      return image?.order || image?.url || index;
    },
    imageSrc(image) {
      if (typeof image === "string") {
        return image;
      }
      return image?.url || "";
    },
  },
  computed: {
    visibleState() {
      if (
        !this.projectionState ||
        this.projectionState.owner !== this.owner ||
        this.projectionState.sessionId !== this.sessionId ||
        (!this.projectionState.text && this.projectionState.images.length === 0)
      ) {
        return null;
      }
      return this.projectionState;
    },
    fsClass() {
      return FONT_SIZES[clampFontSizeIdx(this.visibleState?.fontSizeIdx)];
    },
    sessionId() {
      const session = this.$route.query.session;
      return typeof session === "string" ? session : "";
    },
    formatText() {
      return (text) => {
        if (text !== null) {
          return text.split(/(?:\r\n|\r|\n)/g);
        }
        return [];
      };
    },
  },
  mounted() {
    this.projectionState = readProjectionState();
    this.unsubscribeProjectionState = subscribeProjectionState((state) => {
      this.projectionState = state;
    });
  },
  beforeUnmount() {
    this.unsubscribeProjectionState();
  },
  data() {
    return {
      projectionState: null,
      unsubscribeProjectionState: () => {},
    };
  },
};
</script>

<style scoped>
.live-projector-surface {
  min-height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: transparent;
}

.live-projector-content {
  min-height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 2rem;
  padding: 4vh 5vw;
}

.live-projector-images {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  max-height: 48vh;
}

.live-projector-image {
  max-width: 90vw;
  max-height: 48vh;
  object-fit: contain;
}

.live-projector-text {
  width: 100%;
  overflow-wrap: anywhere;
  line-break: anywhere;
}

.live-projector-text p {
  margin-bottom: 1rem;
}
</style>
