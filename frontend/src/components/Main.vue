<template>
  <div>
    <Header :hideBackBtn="true" :hideHomepageBtn="true"></Header>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card m-3 p-3">
            <div class="row">
              <h1>MeUmy草原提问箱</h1>
            </div>
            <div class="row">
              <!-- TODO: refactor here to automatically add buttons by profiles -->
              <div class="col-6">
                <button
                  class="btn btn-outline-info my-2"
                  value="merry"
                  style="color: #95a0dc; border-color: #95a0dc"
                  v-on:click="newQuestion"
                >
                  咩栗和蜗牛姐姐的棉花糖
                </button>
              </div>
              <div class="col-6">
                <button
                  class="btn btn-outline-danger my-2"
                  value="umy"
                  style="color: #b15158; border-color: #b15158"
                  v-on:click="newQuestion"
                >
                  呜米和妹妹的棉花糖
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="row">
        <div class="col-12">
          <div class="card m-3 p-3">
            <div class="row m-3">
              <h4>查询之前的投稿？</h4>
            </div>
            <form class="row">
              <div class="col-12">
                <input
                  v-model="token"
                  placeholder="请输入神秘代码"
                  v-on:keyup="makeSubmitClickable"
                />
              </div>
              <div class="col-12">
                <button
                  type="button"
                  :class="[submitBtnStyleClasses, submitBtnActiveClass]"
                  v-on:click="checkToken"
                >
                  提交
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
export default {
  name: "Main",
  components: { Header },
  methods: {
    makeSubmitClickable() {
      this.token.length > 0
        ? (this.submitBtnActiveClass = "")
        : (this.submitBtnActiveClass = "disabled");
    },
    checkToken() {
      const authTokenHeader = {
        headers: { Authorization: `Bearer ${this.token}` },
      };
      this.axios
        .get("/api/owner", authTokenHeader)
        .then((resp) => {
          if (resp.data.owner != "") {
            this.$router.push({
              name: "owners",
              params: { owner: resp.data.owner },
              query: { token: this.token.replace(/\s/g, "") },
            });
          } else {
            console.log("something is wrong");
          }
        })
        .catch((err) => {
          if (err.response.status === 401) {
            this.$router.push({
              name: "question",
              query: { token: this.token.replace(/\s/g, "") },
            });
          } else {
            alert("提问箱好像坏掉了，请通知管理员前来查看！");
          }
        });
    },
    newQuestion(event) {
      // TODO: consider moving generating new token logic to the new question page, not here
      this.axios.get("/api/new").then((resp) => {
        this.$router.push({
          name: "question-new",
          query: { token: resp.data.token, owner: event.target.value },
        });
      });
    },
  },
  mounted() {
    let uri = window.location.search.substring(1);
    let params = new URLSearchParams(uri);
    this.token = params.get("token");
    if (this.token != null) {
      this.checkToken();
    }
  },
  data: {
    token: "",
    submitBtnStyleClasses: "my-3 btn btn-outline-primary",
    submitBtnActiveClass: "disabled",
  },
};
</script>
