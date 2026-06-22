<template>
  <div>
    <Header :hideBackBtn="true" :hideHomepageBtn="true"></Header>
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="card shadow-lg my-3 p-3">
            <div class="card-body m-3">
              <div class="row">
                <img
                  v-if="site.hero_image_url"
                  :src="site.hero_image_url"
                  alt=""
                  class="homepage-hero-image"
                />
              </div>
              <div class="row">
                <h1>{{ site.hero_title }}</h1>
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
          <div class="card shadow-lg my-3 p-3">
            <div class="card-body m-1">
              <div class="row">
                <div
                  class="col-12 col-md-6"
                  v-for="entry in ownerList"
                  :key="entry.slug"
                >
                  <button
                    class="btn shadow btn-outline-info my-2 owner-entry-button"
                    :style="setBtnColor(entry.owner)"
                    v-on:click="newQuestion(entry.slug)"
                  >
                    {{ ownerButtonText(entry.owner, entry.slug) }}
                  </button>
                </div>
                <div class="col-12" v-if="ownerList.length === 0">
                  暂无可用提问箱。
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
import { ownerButtonLabel, ownerEntries, siteMetadata } from "../siteConfig.mjs";
let printed = false;
export default {
  name: "Main",
  components: { Header },
  methods: {
    setBtnColor(owner) {
      return {
        color: owner.colors.primary_color,
        "border-color": owner.colors.primary_color,
      };
    },
    ownerButtonText(owner, fallback) {
      return ownerButtonLabel(owner, fallback);
    },
    newQuestion(owner) {
      this.$router.push({
        name: "question-new",
        params: { owner: owner },
      });
    },
  },
  created() {
    this.introductions = this.websiteMetadata.introductions;
    this.site = this.siteMetadata || siteMetadata(this.websiteMetadata);
    this.ownerList = ownerEntries(this.ownerProfiles);
    if (!printed) {
      for (let i in this.websiteMetadata.console_prints) {
        console.log(this.websiteMetadata.console_prints[i]);
      }
      printed = true;
    }
  },
  data() {
    return {
      introductions: [],
      ownerList: [],
      site: siteMetadata(),
    };
  },
};
</script>

<style scoped>
.homepage-hero-image {
  height: 200px;
  max-width: 100%;
  object-fit: contain;
}

.owner-entry-button {
  min-width: 80%;
}
</style>
