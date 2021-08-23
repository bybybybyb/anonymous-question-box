<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <h6 class="card-title m-3">投稿时间：{{ formatTime(asked_at) }}</h6>
            <div class="card-body overflow-auto" style="height: 400px">
              <ul class="list-unstyled m-3" style="line-break: anywhere">
                <li
                  v-for="(sentence, i) in formatText(question_text)"
                  v-bind:key="i"
                  class="text-start"
                  v-html="sentence"
                ></li>
              </ul>
            </div>
          </div>
        </div>
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <h6 class="card-title m-3">
              回复时间： {{ formatTime(answered_at) }}
            </h6>
            <div class="card-body overflow-auto" style="height: 150px">
              <ul class="list-unstyled m-3" style="line-break: anywhere">
                <li
                  v-for="(sentence, i) in formatText(previous_answer_text)"
                  v-bind:key="i"
                  class="text-start"
                  v-html="sentence"
                ></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      <div class="row">
        <div class="card shadow-lg my-3 border">
          <div class="card-body">
            <textarea
              class="col-12"
              rows="8"
              v-model="answer_text"
              v-on:keyup="onNewInput"
              v-on:input="onNewInput"
            ></textarea>
            <button
              class="btn shadow btn-outline-success col-12 col-sm-3"
              v-on:click="submit"
            >
              提交或更新
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
const storagePrefix = "AnswerView_draft_";
export default {
  name: "AnswerView",
  components: { Header },
  props: ["changeQuestion"],
  watch: {
    changeQuestion: function (uuid) {
      this.uuid = uuid;
      this.getQuestionAndAnswer(uuid);
    },
  },
  methods: {
    onNewInput() {
      localStorage.setItem(storagePrefix + this.uuid, this.answer_text);
    },
    getQuestionAndAnswer(uuid) {
      this.answer_text = "";
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      this.axios
        .get("/api/owner/questions/" + uuid, authHeader)
        .then((resp) => {
          this.question_text = resp.data.text;
          this.asked_at = resp.data.asked_at;
          this.previous_answer_text = resp.data.answer;
          this.answer_text = resp.data.answer;
          this.answered_at = resp.data.answered_at;
          if (this.answer_text.length === 0) {
            let localVal = localStorage.getItem(storagePrefix + this.uuid);
            if (localVal && localVal !== "") {
              this.answer_text = localVal;
            }
          }
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
    submit() {
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      this.axios
        .put(
          "/api/owner/questions/" + this.uuid + "/answer",
          {
            uuid: this.uuid,
            answer: this.answer_text,
          },
          authHeader
        )
        .then((resp) => {
          localStorage.removeItem(storagePrefix + this.uuid);
          this.getQuestionAndAnswer(this.uuid);
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
  },
  computed: {
    formatTime() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复";
        }
        return new Date(timeStr).toLocaleString("zh-CN", { hourCycle: "h23" });
      };
    },
    formatText() {
      return (text) => {
        if (text !== null) {
          let sentences = text.split(/(?:\r\n|\r|\n)/g);
          for (var i in sentences) {
            sentences[i] === "" ? (sentences[i] = "<br>") : sentences[i];
          }
          return sentences;
        }
        return [];
      };
    },
  },
  data() {
    return {
      asked_at: "",
      question_text: "",
      answered_at: "",
      previous_answer_text: "",
      answer_text: "",
      uuid: "",
    };
  },
};
</script>
