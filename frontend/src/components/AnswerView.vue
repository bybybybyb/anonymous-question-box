<template>
  <Header :hideHomepageBtn="true"></Header>
  <div class="container">
    <div class="row">
      <div class="col-12 col-md-6">
        <div class="card my-3">
          <div class="card-body">
            <i class="my-3">提交时间：{{ formatTime(asked_at) }}</i>
            <ul class="list-unstyled mx-3 my-3" style="line-break: anywhere">
              <li
                v-for="(sentence, i) in formatText(question_text)"
                v-bind:key="i"
                class="text-start"
              >
                {{ sentence }}
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div class="col-12 col-md-6">
        <div class="card my-3">
          <div class="card-body">
            <i class="my-3">回复时间： {{ formatTime(answered_at) }}</i>
            <ul class="list-unstyled mx-3 my-3" style="line-break: anywhere">
              <li
                v-for="(sentence, i) in formatText(previous_answer_text)"
                v-bind:key="i"
              >
                {{ sentence }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
    <div class="row">
      <div class="card my-3">
        <div class="card-body">
          <textarea class="col-12" rows="10" v-model="answer_text"></textarea>
          <button
            class="btn btn-outline-success col-12 col-sm-3"
            v-on:click="submit"
          >
            提交或更新
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
export default {
  name: "AnswerView",
  components: { Header },
  methods: {
    submit() {
      const authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      this.axios
        .put(
          "/api/owner/questions/" + this.$route.query.uuid + "/answer",
          {
            uuid: this.$route.query.uuid,
            answer: this.answer_text,
          },
          authHeader
        )
        .then((resp) => {
          console.log(resp);
          this.$router.go(0);
        })
        .catch((err) => {
          alert(err.response);
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
        return new Date(timeStr).toLocaleString();
      };
    },
    formatText() {
      return (text) => {
        return text.split(/(?:\r\n|\r|\n)/g);
      };
    },
  },
  created() {
    const authHeader = {
      headers: { Authorization: `Bearer ${this.$route.query.token}` },
    };
    this.axios
      .get("/api/owner/questions/" + this.$route.query.uuid, authHeader)
      .then((resp) => {
        this.question_text = resp.data.text;
        this.asked_at = resp.data.asked_at;
        this.previous_answer_text = resp.data.answer;
        this.answer_text = resp.data.answer;
        this.answered_at = resp.data.answered_at;
      })
      .catch((err) => {
        console.log(err.response);
      });
  },
  data() {
    return {
      asked_at: "",
      question_text: "",
      answered_at: "",
      previous_answer_text: "",
      answer_text: "",
    };
  },
};
</script>
