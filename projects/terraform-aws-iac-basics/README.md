# Terraformで構築するALBとprivate subnetのEC2

`asamomiji.jp`の記事「TerraformでAWSリソースをIaC化する」の完全版Terraform設定です。東京リージョンの2つのAvailability Zoneにpublic subnetとprivate subnetを配置し、internet-facing ALBからprivate subnetのEC2 2台へHTTPリクエストを転送します。

掲載予定先：<https://asamomiji.jp/articles/terraform-aws-iac-basics/>（2026年9月時点では未公開）

## 構成

- VPC：`10.0.0.0/16`
- public subnet：`10.0.1.0/24`、`10.0.2.0/24`
- private subnet：`10.0.11.0/24`、`10.0.12.0/24`
- Internet Gateway：1個
- zonal NAT Gateway：public subnet aに1台
- ALB：public subnet 2個を使用するinternet-facing ALB
- EC2：各private subnetにAmazon Linux 2023 x86_64のインスタンスを1台
- Security Group：ALB用とEC2用を分離

この構成では学習用に費用を抑えるため、NAT Gatewayを1台だけ使用します。private subnet cからの外向き通信もAZ aのNAT Gatewayを通るため、単一障害点になり、AZ間データ転送料金も発生し得ます。本番構成では要件に応じてAZごとのNAT Gateway、Auto Scaling、HTTPS、監視などを設計してください。

## 必要な環境

- Terraform CLI 1.10以上、2.0未満
- HashiCorp AWS Provider 6.x
- AWS CLI v2
- 東京リージョンでVPC、EC2、ELB、Elastic IPなどを作成・削除できるAWS認証情報
- 東京リージョンで利用できるAmazon Linux 2023 x86_64 AMI ID

ALB、NAT Gateway、EC2、公開IPv4アドレスなどには料金が発生します。実行前にAWS料金計算ツールで確認し、検証後は`terraform destroy`相当の手順で構成全体を削除してください。

## 入力値の準備

見本をコピーします。`terraform.tfvars`はGit管理対象外です。

```console
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars`の次の値を実環境に合わせて変更します。

- `ami_id`：東京リージョンで利用できるAmazon Linux 2023 x86_64 AMI ID
- `allowed_ingress_cidr`：動作確認する端末の公開IPv4アドレスへ`/32`を付けたCIDR

認証情報はTerraform設定へ記述しません。IAM Identity Centerのプロファイルを使う場合は、次のように認証先を確認します。

```console
export AWS_PROFILE=terraform-sandbox
aws sso login --profile "$AWS_PROFILE"
aws sts get-caller-identity
```

## 検証と作成

このディレクトリで実行します。

```console
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=create.tfplan
terraform show create.tfplan
```

planで想定外の変更や削除がないことを確認してから、保存した計画を適用します。保存済みplanを指定した場合、追加の確認プロンプトは表示されません。

```console
terraform apply create.tfplan
terraform output -raw alb_url
curl --fail --show-error "$(terraform output -raw alb_url)"
```

EC2のuser dataとALBのヘルスチェックが完了するまで時間がかかります。AWSコンソールなどで両方のターゲットが`healthy`であることも確認してください。

## 削除

作成時と同じディレクトリ、state、AWS認証先を使います。

```console
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
```

削除後はAWS側でもALB、EC2、NAT Gateway、Elastic IP、関連EBSボリュームなどが残っていないことを確認してください。

## 検証記録

- 2026年9月23日：Terraform CLI 1.16.3で`terraform fmt -check -recursive`に合格
- 2026年9月23日：`terraform init -backend=false`でHashiCorp AWS Provider 6.66.0を選択し、`terraform validate`に合格
- 2026年9月23日：東京リージョンのAmazon Linux 2023 x86_64 AMIと文書用IPv4 CIDRを指定し、AWSへ接続した`terraform plan`に成功。結果は29 to add、0 to change、0 to destroy
- AWS上でのapply、疎通、再plan、destroyは未実施

planでは、VPC 1個、public/private subnet各2個、Internet Gateway 1個、zonal NAT Gateway 1個、EC2 2台、ALB 1台と、その通信に必要なルート、Security Group規則、ターゲットグループ、リスナーがすべて新規作成として計画されることを確認しました。AMI ID、確認端末のCIDR、AWSアカウントIDなど、実行環境を識別する値は収録していません。

## 来歴、第三者要素、ライセンス

- 2026年9月、記事用の新規サンプルとして作成した所有者管理コードです。
- AWSやHashiCorpのコード、画像、設定ファイルを複製していません。
- 認証情報、個人情報、AWSアカウントID、実在環境のIPアドレスを収録しません。
- 第三者コードおよび第三者メディアは含みません。
- リポジトリルートのBSD 2-Clause Licenseを適用します。
