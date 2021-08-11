<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12 col-md-6">
          <div class="card my-3" style="background: rgba(255, 255, 255, 0.9)">
            <div class="card-body">
              <div class="card">
                <div class="card-body overflow-auto" style="max-height: 300px">
                  <i class="my-3">提交时间：{{ formatTime(asked_at) }}</i>
                  <ul
                    class="list-unstyled mx-3 my-3"
                    style="line-break: anywhere"
                  >
                    <li
                      v-for="(sentence, i) in formatText(question_text)"
                      v-bind:key="i"
                    >
                      <p>{{ sentence }}</p>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div class="card my-3" style="background: rgba(255, 255, 255, 0.9)">
            <div class="card-body">
              <div class="card">
                <div class="card-body overflow-auto" style="max-height: 300px">
                  <i class="my-3">回复时间： {{ formatTime(answered_at) }}</i>
                  <ul
                    class="list-unstyled mx-3 my-3"
                    style="line-break: anywhere"
                  >
                    <li
                      v-for="(sentence, i) in formatText(answer_text)"
                      v-bind:key="i"
                    >
                      <p>{{ sentence }}</p>
                    </li>
                  </ul>
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
export default {
  name: "QuestionDisplay",
  props: {
    question_text: String,
    asked_at: String,
    answer_text: String,
    answered_at: String,
  },
  computed: {
    formatTime() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复，请耐心等待哦。";
        }
        return new Date(timeStr).toLocaleString();
      };
    },
    formatText() {
      return (text) => {
        return text.split(/(?:\r\n|\r|\n)/g);
      };
    },
  },
  beforeCreate() {},
  data() {
    return {};
  },
};
</script>
