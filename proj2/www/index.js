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

function show_pm(div_id, prefix, id)
{
  div = document.getElementById(div_id);
  potential = div.getElementsByTagName("div");
  for (var i=0; i < potential.length; i++)
  {
    if (potential[i].id.startsWith(prefix))
    {
      if (potential[i].id == (prefix + "-" + id))
      {
        potential[i].style = "";
      } else {
        potential[i].style = "display: none";
      }
    }
  }
}
