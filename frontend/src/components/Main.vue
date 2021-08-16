<template>
  <div>
    <Header :hideBackBtn="true" :hideHomepageBtn="true"></Header>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg m-3 p-3">
            <div class="card-body m-3">
              <div class="row">
                <img src="../assets/marshmallow.svg" alt="" height="200" />
              </div>
              <div class="row">
                <h1>MeUmy的棉花糖</h1>
              </div>
              <div class="row">
                <ul class="list-unstyled">
                  <li class="m-2" v-for="str in introductions" :key="str">
                    {{ str }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
          <div class="card shadow-lg m-3 p-3">
            <div class="card-body m-1">
              <div class="row">
                <!-- TODO: refactor here to automatically add buttons by profiles -->
                <div class="col-12 col-sm-6">
                  <button
                    class="btn shadow btn-outline-info my-2"
                    :style="setBtnColor('merry')"
                    v-on:click="newQuestion('merry')"
                  >
                    咩栗和蜗牛姐姐的棉花糖
                  </button>
                </div>
                <div class="col-12 col-sm-6">
                  <button
                    class="btn shadow btn-outline-danger my-2"
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
  </div>
</template>

<script>
import Header from "./Header.vue";
let printed = false;
export default {
  name: "Main",
  components: { Header },
  methods: {
    setBtnColor(owner) {
      return {
        color: this.ownerProfiles[owner].colors.primary_color,
        "border-color": this.ownerProfiles[owner].colors.primary_color,
      };
    },
    newQuestion(owner) {
      this.$router.push({
        name: "question-new",
        params: { owner: owner },
      });
    },
  },
  created() {
    this.axios
      .get("/api/metadata")
      .then((resp) => {
        this.introductions = resp.data.introductions;
        if (!printed) {
          for (let i in resp.data.console_prints) {
            console.log(resp.data.console_prints[i]);
          }
          printed = true;
        }
      })
      .catch((err) => {
        console.log(err.response);
      });
  },
  data: {
    introductions: [],
  },
};
</script>
