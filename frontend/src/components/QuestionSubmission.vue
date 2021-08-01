<template>
  <Header :hideBackBtn="true"></Header>
  <div class="container">
    <div class="card my-3">
      <div class="card-body">
        <h1>感谢投稿！</h1>
        <div class="contaienr">
          <p class="mx-3">
            请妥善保存下方二维码或神秘代码，这将是你找回投稿的唯一方式！
          </p>
          <p class="mx-3">记得时不时来看一眼有没收到回复哦~</p>
          <qrcode-vue
            class="col-6 my-4"
            :value="question_url"
            :size="200"
          ></qrcode-vue>
          <p>神秘代码：</p>
          <div class="col-md-12">
            <p style="line-break: anywhere">{{ $route.query.token }}</p>
          </div>
          <button
            class="col-6 btn btn-outline-info col-sm-2"
            v-on:click="goToQuestion"
          >
            查看刚提交的投稿
          </button>
          <h5 class="m-3">想要继续投稿？请点击返回主页重新开始！</h5>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import QrcodeVue from "qrcode.vue";
import Header from "./Header.vue";

export default {
  name: "QuestionSubmission",
  components: {
    QrcodeVue,
    Header,
  },
  computed: {},
  methods: {
    goToQuestion(event) {
      this.$router.push({
        name: "question",
        query: { token: this.token },
      });
    },
  },
  created() {
    this.question_url =
      window.location.host + "?token=" + this.$route.query.token;
    this.token = this.$route.query.token;
  },
  data() {
    return {
      type: "normal",
      question_text: "",
      asked_at: "",
      answer_text: "",
      answered_at: "",
      new_question_text: "",
      currentLength: 0,
      maxLength: 500,
      submitBtnStyleClasses: "btn btn-outline-success col-12",
      submitBtnActiveClass: "disabled",
      question_url: "",
      token: "",
    };
  },
};
</script>
