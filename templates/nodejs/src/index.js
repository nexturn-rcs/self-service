const express = require('express')
const client = require('prom-client')

const app = express()
const port = process.env.PORT || 3000

const register = new client.Registry()
client.collectDefaultMetrics({ register })

const requestCounter = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  registers: [register]
})

app.get('/', (req, res) => {
  requestCounter.inc()
  res.json({ message: '${{ values.repoName }} is running' })
})

app.get('/health', (req, res) => {
  requestCounter.inc()
  res.json({ status: 'UP' })
})

app.get('/ready', (req, res) => {
  requestCounter.inc()

  // Add dependency checks here later
  // Database
  // Redis
  // External APIs

  res.json({ status: 'READY' })
})

app.get('/info', (req, res) => {
  requestCounter.inc()
  res.json({
    service: '${{ values.repoName }}',
    version: '1.0.0',
    environment: process.env.APP_ENV || 'unknown'
  })
})

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType)
  res.end(await register.metrics())
})

app.listen(port, () => {
  console.log(`${{ values.repoName }} listening on port ${port}`)
})

module.exports = app
