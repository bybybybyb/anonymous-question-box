<template>
  <nav class="navbar navbar-expand-md navbar-dark bg-dark" id="site-header">
    <div class="container-fluid">
      <span class="navbar-brand m-1 mb-0 h1">
        <img v-if="site.header_logo_url" :src="site.header_logo_url" alt="" height="20" />
        <router-link
          class="m-1"
          to="/"
          style="text-decoration: none; color: inherit"
          >{{ site.header_title }}</router-link
        >
      </span>
      <ul class="navbar-nav mb-2 mb-lg-0">
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-warning"
            :class="{ 'd-none': hideHomepageBtn }"
            v-on:click="goHome"
          >
            返回主页
          </button>
        </li>
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-info"
            :class="{ 'd-none': hideBackBtn }"
            v-on:click="goBack"
          >
            返回上一页
          </button>
        </li>
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-light"
            :class="{ 'd-none': !adminContactLink }"
            v-on:click="contactAdmin"
          >
            联系管理员
          </button>
        </li>
      </ul>
    </div>
  </nav>
</template>

<script>
import { siteMetadata } from "../siteConfig.mjs";

export default {
  name: "Header",
  props: {
    hideHomepageBtn: Boolean,
    hideBackBtn: Boolean,
  },
  methods: {
    goHome() {
      this.$router.push({ path: "/" });
    },
    goBack() {
      this.$router.go(-1);
    },
    contactAdmin() {
      if (this.adminContactLink) {
        window.open(this.adminContactLink);
      }
    },
  },
  created() {
    this.site = this.siteMetadata || siteMetadata(this.websiteMetadata || {});
    this.adminContactLink = this.websiteMetadata?.admin?.link || "";
  },
  data() {
    return {
      site: siteMetadata(),
      adminContactLink: "",
    };
  },
};
</script>
