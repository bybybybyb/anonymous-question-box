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
                  :style="setBtnColor('merry')"
                  v-on:click="newQuestion('merry')"
                >
                  咩栗和蜗牛姐姐的棉花糖
                </button>
              </div>
              <div class="col-6">
                <button
                  class="btn btn-outline-danger my-2"
                  :style="setBtnColor('umy')"
                  v-on:click="newQuestion('umy')"
                >
                  呜米和妹妹的棉花糖
                </button>
              </div>
            </div>
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
    setBtnColor(owner) {
      return {
        color: this.ownerProfiles[owner].color_theme.primary_color,
        "border-color": this.ownerProfiles[owner].color_theme.primary_color,
      };
    },
    newQuestion(owner) {
      this.$router.push({
        name: "question-new",
        params: { owner: owner },
      });
    },
  },
  data: {
    submitBtnStyleClasses: "my-3 btn btn-outline-primary",
    submitBtnActiveClass: "disabled",
  },
};
</script>
