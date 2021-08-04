import './index.css'
import "bootstrap/dist/css/bootstrap.min.css"
import "bootstrap"
import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import axios from 'axios'
import VueAxios from 'vue-axios'
import App from './App.vue'
import OwnerView from "./components/OwnerView.vue";
import QuestionNew from "./components/QuestionNew.vue";
import QuestionView from "./components/QuestionView.vue";
import AnswerView from "./components/AnswerView.vue";
import LiveView from "./components/LiveView.vue";
import Main from "./components/Main.vue";

const routes = [
  { name: "homepage", path: "/", component: Main },
  { name: "owners", path: "/owner/:owner/dashboard", component: OwnerView, props: true },
  { name: "live", path: "/owner/:owner/live", component: LiveView, props: true },
  { name: "question", path: "/question", component: QuestionView, props: true },
  { name: "question-new", path: "/question/:owner/new", component: QuestionNew, props: true },
  { name: "answer", path: "/question/answer", component: AnswerView, props: true },
  { path: "/:catchAll(.*)", redirect: "/" },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

(async () => {
  await axios
    .get("/api/profiles").then((resp) => {
      const profiles = resp.data;
      const profileProvider = {
        name: "ProfileProvider",
        data() {
          return {
            ownerProfiles: profiles,
          };
        },
      }
      const app = createApp(App);
      app.use(VueAxios, axios);
      app.use(router);
      app.mixin(profileProvider);
      app.mount('#app');
    }).catch((err) => {
      console.log(err.response);
    });
})()

