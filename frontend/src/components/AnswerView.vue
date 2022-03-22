<template>
  <div>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <h6 class="card-title m-3">投稿时间：{{ asked_at }}</h6>
            <div class="card-body overflow-auto">
              <div class="container">
                <div class="row">
                  <div class="col-12" v-if="images.length > 0">
                    <image-display
                      :images="images"
                      slideHeight="300px"
                      :withNavigation="false"
                    />
                  </div>
                  <div
                    class="col-12 mt-3 d-flex justify-content-end"
                    v-if="images.length > 0"
                  >
                    <button
                      class="btn btn-outline-info btn-sm"
                      v-on:click="toFullscreen()"
                    >
                      图片全屏
                    </button>
                  </div>
                  <div class="col-12 mt-3">
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
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-12">
          <div class="card shadow-lg my-3">
            <h6 class="card-title m-3" v-if="answered_at !== ''">
              回复时间： {{ answered_at }}
            </h6>
            <h6 class="card-title m-3" v-else>回复时间： 尚未回复</h6>
            <h6 class="card-title m-3" v-if="visit_count > 0">
              最近查看时间： {{ last_visited_at }}, 总查看次数：
              {{ visit_count }}
            </h6>
            <div class="card-body overflow-auto" style="height: 150px">
              <div style="line-break: anywhere">
                <p
                  v-for="(sentence, i) in formatText(previous_answer_text)"
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
import ImageDisplay from "./ImageDisplay.vue";
const storagePrefix = "AnswerView_draft_";
export default {
  name: "AnswerView",
  components: { Header, ImageDisplay },
  props: { changeQuestion: String },
  emits: ["fullscreenImg"],
  watch: {
    changeQuestion: function (uuid) {
      this.uuid = uuid;
      this.getQuestionAndAnswer(uuid);
    },
  },
  methods: {
    toFullscreen() {
      this.$emit("fullscreenImg", this.images);
    },
    onNewInput() {
      localStorage.setItem(storagePrefix + this.uuid, this.answer_text);
    },
    formatTime(timeStr) {
      let time = Date.parse(timeStr);
      if (time === 0) {
        return "";
      }
      return new Date(timeStr).toLocaleString("zh-CN", { hourCycle: "h23" });
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
          this.asked_at = this.formatTime(resp.data.asked_at);
          this.previous_answer_text = resp.data.answer;
          this.answer_text = resp.data.answer;
          this.answered_at = this.formatTime(resp.data.answered_at);
          this.last_visited_at = this.formatTime(resp.data.last_visited_at);
          this.visit_count = resp.data.visit_count;
          this.images = resp.data.images;
          if (this.answer_text.length === 0) {
            let localVal = localStorage.getItem(storagePrefix + this.uuid);
            if (localVal && localVal !== "") {
              this.answer_text = localVal;
            }
          }
        })
        .catch((err) => {
          console.log(err);
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
            answered_by: "manual",
          },
          authHeader
        )
        .then(() => {
          localStorage.removeItem(storagePrefix + this.uuid);
          this.getQuestionAndAnswer(this.uuid);
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
  },
  computed: {
    formatText() {
      return (text) => {
        if (text !== null) {
          return text.split(/(?:\r\n|\r|\n)/g);
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
      last_visited_at: "",
      visit_count: 0,
      uuid: "",
      images: [],
    };
  },
};
</script>
