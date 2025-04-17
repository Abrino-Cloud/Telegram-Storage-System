<template>
  <div class="app-wrapper">
    <Navbar v-if="isAuthenticated" />
    
    <div class="main-content">
      <router-view />
    </div>
    
    <footer class="footer">
      <div class="container">
        <p>AbrinoStorage - Telegram Storage System</p>
      </div>
    </footer>
    
    <Notifications />
  </div>
</template>

<script>
import { computed, onMounted } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import Navbar from '@/components/Navbar.vue';
import Notifications from '@/components/Notifications.vue';

export default {
  name: 'App',
  components: {
    Navbar,
    Notifications
  },
  setup() {
    const store = useStore();
    const router = useRouter();
    
    const isAuthenticated = computed(() => store.getters['auth/isAuthenticated']);
    
    onMounted(async () => {
      // Check if user is authenticated
      const token = localStorage.getItem('token');
      if (token) {
        // Validate token and get user profile
        try {
          await store.dispatch('auth/fetchUserProfile');
        } catch (error) {
          // Token is invalid, redirect to login
          localStorage.removeItem('token');
          router.push('/login');
        }
      }
    });
    
    return {
      isAuthenticated
    };
  }
};
</script>

<style>
:root {
  --primary-color: #3498db;
  --secondary-color: #2ecc71;
  --dark-color: #2c3e50;
  --light-color: #ecf0f1;
  --danger-color: #e74c3c;
  --warning-color: #f39c12;
  --success-color: #27ae60;
  --info-color: #3498db;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  background-color: #f5f5f5;
  color: #333;
}

.app-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  padding: 20px;
  margin-top: 60px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.footer {
  background-color: var(--dark-color);
  color: #fff;
  padding: 20px 0;
  text-align: center;
}

.btn {
  display: inline-block;
  padding: 8px 16px;
  background-color: var(--primary-color);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  font-size: 14px;
}

.btn:hover {
  background-color: #2980b9;
}

.btn-success {
  background-color: var(--success-color);
}

.btn-success:hover {
  background-color: #219a52;
}

.btn-danger {
  background-color: var(--danger-color);
}

.btn-danger:hover {
  background-color: #c0392b;
}

.card {
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 20px;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-control {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

.form-label {
  display: block;
  margin-bottom: 5px;
  font-weight: 600;
}

.alert {
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 15px;
}

.alert-success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.alert-danger {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.alert-warning {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeeba;
}

.alert-info {
  background-color: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}
</style>