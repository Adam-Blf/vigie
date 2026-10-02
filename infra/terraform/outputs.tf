output "public_ip" {
  description = "Public IP of the node. Never paste it into docs, proofs or screenshots."
  value       = oci_core_instance.vigie.public_ip
}

output "ssh_command" {
  description = "SSH access with the dedicated deploy key."
  value       = "ssh -i ~/.ssh/vigie_deploy ubuntu@${oci_core_instance.vigie.public_ip}"
}

output "kube_tunnel_command" {
  description = "Opens the Kubernetes API on localhost:6443 through SSH, since 6443 is never public."
  value       = "ssh -i ~/.ssh/vigie_deploy -N -L 6443:127.0.0.1:6443 ubuntu@${oci_core_instance.vigie.public_ip}"
}
