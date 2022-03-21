<template>
  <div class="container">
    <div class="row">
      <div class="col-md-6 col-12">
        <div
          class="card shadow-lg my-3"
          style="background: rgba(255, 255, 255, 0.9)"
        >
          <div class="card-body">
            <div class="card">
              <h5 class="card-title mt-3">您的投稿</h5>
              <h6>投稿类型： {{ receiver }}</h6>
              <div
                class="card-body overflow-auto"
                :style="{
                  'max-height': questionCardMaxHeight + 'px',
                }"
              >
                <div class="container">
                  <div class="row">
                    <div class="col-12">
                      <image-display
                        :images="images"
                        :slideHeight="questionCardMaxHeight - 200 + 'px'"
                        :enableClickToFullscreen="true"
                      />
                    </div>
                    <div class="col-12 mt-3">
                      <div
                        :style="{
                          'line-break': 'anywhere',
                        }"
                        ref="questionText"
                      >
                        <p
                          v-for="(sentence, i) in formatText(question_text)"
                          v-bind:key="i"
                          class="lh-lg text-start"
                        >
                          {{ sentence }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="card-footer" v-show="isLongText">
                <label
                  class="btn btn-outline-primary btn-sm"
                  v-on:click="textCardShowAllToggle"
                >
                  {{ showAllToggleText }}
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-6 col-12">
        <div
          class="card shadow-lg my-3"
          style="background: rgba(255, 255, 255, 0.9)"
        >
          <div class="card-body">
            <div class="card">
              <h5 class="card-title m-3">
                {{ generateAnswerTitle(answered_at) }}
              </h5>
              <div class="card-body overflow-auto" style="max-height: 500px">
                <div style="line-break: anywhere">
                  <p
                    v-for="(sentence, i) in formatText(answer_text)"
                    v-bind:key="i"
                    class="lh-lg text-start"
                  >
                    {{ sentence }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const defaultCardMaxHeight = 500;
import ImageDisplay from "./ImageDisplay.vue";
export default {
  name: "QuestionDisplay",
  components: {
    ImageDisplay,
  },
  props: {
    receiver: String,
    question_text: String,
    asked_at: String,
    answer_text: String,
    answered_at: String,
    images: Array,
  },
  computed: {
    generateAnswerTitle() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复，请耐心等待。";
        }
        return "回信";
      };
    },
    formatText() {
      return (text) => {
        if (text !== null) {
          return text.split(/(?:\r\n|\r|\n)/g);
        }
        return [];
      };
    },
    textCardShowAllToggle() {
      return () => {
        this.questionCardMaxHeight =
          this.questionCardMaxHeight === defaultCardMaxHeight
            ? 10000
            : defaultCardMaxHeight;
        this.showAllToggleText =
          this.showAllToggleText === "展开显示" ? "收缩显示" : "展开显示";
      };
    },
  },
  updated() {
    this.isLongText =
      this.$refs.questionText.clientHeight > defaultCardMaxHeight;
  },
  data() {
    return {
      questionCardMaxHeight: defaultCardMaxHeight,
      showAllToggleText: "展开显示",
      isLongText: false,
    };
  },
};
</script>
