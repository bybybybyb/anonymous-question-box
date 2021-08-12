<template>
  <div>
    <div class="container">
      <div
        class="card shadow-lg my-3"
        style="background: rgba(255, 255, 255, 0.9)"
      >
        <div class="card-body">
          <div class="card">
            <div class="card-body">
              <h1>感谢投稿！</h1>
              <div class="contaienr">
                <p class="mx-3">
                  请妥善保存下方二维码和链接，这将是你找回投稿的唯一方式！
                </p>
                <p class="mx-3">记得时不时来看一眼有没收到回复哦~</p>
                <qrcode-vue
                  class="col-6 my-4"
                  :value="question_url"
                  :size="200"
                ></qrcode-vue>
                <div class="col-md-12">
                  <router-link
                    :to="{ name: 'question', query: { token: token } }"
                    >请右键或长按复制本链接！</router-link
                  >
                </div>
                <h5 class="m-3">想要继续投稿？请点击返回主页重新开始！</h5>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import QrcodeVue from "qrcode.vue";

export default {
  name: "QuestionSubmission",
  components: {
    QrcodeVue,
  },
  props: {
    token: String,
  },
  created() {
    let ref = this.$router.resolve({
      query: { token: this.token },
    });
    this.question_url = "https://" + window.location.host + "/" + ref.href;
  },
  data() {
    return {
      question_url: "",
    };
  },
};
</script>
