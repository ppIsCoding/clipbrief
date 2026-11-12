param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('chen', 'pan', 'xu')]
    [string]$Who,

    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string[]]$Paths
)

$authors = @{
    chen = @{ Name = '陈博涵'; Email = 'chenbohan@example.com' }
    pan  = @{ Name = '潘少杰'; Email = 'panshaojie@example.com' }
    xu   = @{ Name = '徐子昂'; Email = 'xuziang@example.com' }
}

$author = $authors[$Who]

if ($Paths) {
    git add -- $Paths
}

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Error '没有暂存的改动，先指定 -Paths 或手动 git add'
    exit 1
}

$env:GIT_COMMITTER_NAME = $author.Name
$env:GIT_COMMITTER_EMAIL = $author.Email

git commit --author="$($author.Name) <$($author.Email)>" -m $Message

Write-Host "已提交，作者：$($author.Name) <$($author.Email)>"
git log -1 --format='%h %an <%ae> %s'
