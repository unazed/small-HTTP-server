function show_info(post_count, creator_ip)
{
  document.getElementById("post_count").textContent = "Posts: " + post_count;
  document.getElementById("creator_ip").textContent = "Author: " + creator_ip;
}

function clear_info()
{
  document.getElementById("post_count").textContent = "Posts: n/a";
  document.getElementById("creator_ip").textContent = "Author: n/a";
}
