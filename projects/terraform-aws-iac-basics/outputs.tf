output "alb_url" {
  description = "動作確認用のHTTP URL"
  value       = "http://${aws_lb.web.dns_name}"
}
