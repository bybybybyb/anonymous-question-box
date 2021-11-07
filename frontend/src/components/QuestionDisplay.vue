<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12 col-md-6">
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
                  :style="{ 'max-height': maxHeight + 'px' }"
                >
                  <div style="line-break: anywhere">
                    <p
                      v-for="(sentence, i) in formatText(question_text)"
                      v-bind:key="i"
                      class="lh-lg text-start"
                    >
                      {{ sentence }}
                    </p>
                  </div>
                </div>
                <button
                  class="btn btn-outline-primary btn-sm mx-5 my-3"
                  v-on:click="textCardShowAllToggle"
                >
                  {{ showAllToggleText }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div
            class="card shadow-lg my-3"
            style="background: rgba(255, 255, 255, 0.9)"
          >
            <div class="card-body">
              <div class="card">
                <h5 class="card-title m-3">
                  {{ generateAnswerTitle(answered_at) }}
                </h5>
                <div class="card-body overflow-auto" style="max-height: 300px">
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
  </div>
</template>

<script>
const defaultTextCardMaxHeight = 300;
export default {
  name: "QuestionDisplay",
  props: {
    receiver: String,
    question_text: String,
    asked_at: String,
    answer_text: String,
    answered_at: String,
  },
  computed: {
    generateAnswerTitle() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复，请耐心等待哦。";
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
        this.maxHeight =
          this.maxHeight === defaultTextCardMaxHeight
            ? 10000
            : defaultTextCardMaxHeight;
        this.showAllToggleText =
          this.showAllToggleText === "展开全部" ? "收缩显示" : "展开全部";
      };
    },
  },
  beforeCreate() {},
  data() {
    return {
      maxHeight: defaultTextCardMaxHeight,
      showAllToggleText: "展开全部",
    };
  },
};
</script>
