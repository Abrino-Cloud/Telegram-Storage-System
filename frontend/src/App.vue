<template>
  <div class="app-wrapper">
    <header class="header">
      <div class="container">
        <h1>Telegram Storage System</h1>
      </div>
    </header>
    
    <div class="main-content">
      <router-view />
    </div>
    
    <footer class="footer">
      <div class="container">
        <p>AbrinoStorage - Telegram Storage System</p>
      </div>
    </footer>
  </div>
</template>

<script>
export default {
  name: 'App'
}
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

.header {
  background-color: var(--primary-color);
  color: white;
  padding: 1rem 0;
  text-align: center;
}

.main-content {
  flex: 1;
  padding: 20px;
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
</style>
