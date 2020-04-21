// Initializing a class definition
class HierarchicalBarChart extends VerticalBarChart{
    constructor(container_name, data) {
        super(container_name, data);

    }

    init(){
        this.duration = 500
    }

    transformData(data){
        return d3.hierarchy(data)
            .sort((a, b) => b.value - a.value)
            .eachAfter(d => d.index = d.parent ? d.parent.index = d.parent.index + 1 || 0 : 0)
    }

    computeMaxXDomain() {
        return this.root.value;
    }

    buildSVG(){
        this.svg = this.container.append("svg")
            .attr("preserveAspectRatio", "xMinYMin meet")
            .attr("viewBox", "0 0 " + this.width + " " + this.height);
        this.svg.append("rect")
            .attr("class", "background")
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .attr("width", this.width)
            .attr("height", this.height)
            .attr("cursor", "pointer")
            .on("click", d => this.up(d));
        this.xAxis = g => g
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.margin.top})`)
            .call(d3.axisTop(this.x).ticks(this.width / 80, "s"))
            .call(g => (g.selection ? g.selection() : g).select(".domain").remove())
        this.yAxis = g => g
            .attr("class", "y-axis")
            .attr("transform", `translate(${this.margin.left + 0.5},0)`)
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("y1", this.margin.top)
                .attr("y2", this.height - this.margin.bottom))
        this.svg.append("g")
            .call(this.xAxis);

        this.svg.append("g")
            .call(this.yAxis);
        this.down(this.root);
    }

    getHeight(){
        let max = 1;
        this.root.each(d => d.children && (max = Math.max(max, d.children.length)));
        return max * this.barStep + this.margin.top + this.margin.bottom;
    }

    up(d) {
        if (!d.parent || !this.svg.selectAll(".exit").empty()) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d.parent);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();

        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");

        // Update the x-scale domain.
        this.x.domain([0, d3.max(d.parent.children, d => d.value)]);

        // Update the x-axis.
        this.svg.selectAll(".x-axis").transition(transition1)
            .call(this.xAxis);

        // Transition exiting bars to the new x-scale.
        exit.selectAll("g").transition(transition1)
            .attr("transform", stagger(this.x, this.barStep));

        // Transition exiting bars to the parent’s position.
        exit.selectAll("g").transition(transition2)
            .attr("transform", stack(d.index, this.x, this.barStep));

        // Transition exiting rects to the new scale and fade to parent color.
        exit.selectAll("rect").transition(transition1)
            .attr("width", d => this.x(d.value) - this.x(0))
            .attr("fill", this.color(true));

        // Transition exiting text to fade out.
        // Remove exiting nodes.
        exit.transition(transition2)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data's parent.
        const enter = this.createBar(d.parent, ".exit")
            .attr("fill-opacity", 0);

        enter.selectAll("g")
            .attr("transform", (d, i) => `translate(0,${this.barStep * i})`);

        // Transition entering bars to fade in over the full duration.
        enter.transition(transition2)
            .attr("fill-opacity", 1);

        // Color the bars as appropriate.
        // Exiting nodes will obscure the parent bar, so hide it.
        // Transition entering rects to the new x-scale.
        // When the entering parent rect is done, make it visible!
        enter.selectAll("rect")
            .attr("fill", d => this.color(!!d.children))
            .attr("fill-opacity", p => p === d ? 0 : null)
            .transition(transition2)
            .attr("width", d => this.x(d.value) - this.x(0))
            .on("end", function(p) { d3.select(this).attr("fill-opacity", 1); });
    }

    down(d) {
        if (!d.children || d3.active(this.svg.node())) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();

        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");

        // Entering nodes immediately obscure the clicked-on bar, so hide it.
        exit.selectAll("rect")
            .attr("fill-opacity", p => p === d ? 0 : null);

        // Transition exiting bars to fade out.
        exit.transition(transition1)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data.
        // Per above, entering bars are immediately visible.
        const enter = this.createBar(d, ".y-axis")
            .attr("fill-opacity", 0);

        // Have the text fade-in, even though the bars are visible.
        enter.transition(transition1)
            .attr("fill-opacity", 1);

        // Transition entering bars to their new y-position.
        enter.selectAll("g")
            .attr("transform", stack(d.index, this.x, this.barStep))
            .transition(transition1)
            .attr("transform", stagger(this.x, this.barStep));

        // Update the x-scale domain.
        this.x.domain([0, d3.max(d.children, d => d.value)]);

        // Update the x-axis.
        this.svg.selectAll(".x-axis").transition(transition2)
            .call(this.xAxis);

        // Transition entering bars to the new x-scale.
        enter.selectAll("g").transition(transition2)
            .attr("transform", (d, i) => `translate(0,${this.barStep * i})`);

        // Color the bars as parents; they will fade to children if appropriate.
        enter.selectAll("rect")
            .attr("fill", this.color(true))
            .attr("fill-opacity", 1)
            .transition(transition2)
            .attr("fill", d => this.color(!!d.children))
            .attr("width", d => this.x(d.value) - this.x(0));
    }

    // Creates a set of bars for the given data node, at the specified index.
    createBar(d, selector) {
        let chart = this;
        const g = this.svg.insert("g", selector)
            .attr("class", "enter")
            .attr("transform", `translate(0,${this.margin.top + this.barStep * this.barPadding})`)
            .attr("text-anchor", "end")
            .style("font", "14px sans-serif").style('fill', 'cornsilk');

        const bar = g.selectAll("g")
            .data(d.children)
            .join("g")
            .attr("cursor", d => !d.children ? null : "pointer")
            .on("click", d => this.down(d));

        bar.append("text")
            .attr("x", this.margin.left - 6)
            .attr("y", this.barStep * (1 - this.barPadding) / 2)
            .attr("dy", ".35em")
            .text(d => d.data.name).style('fill', 'cornsilk');

        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function(d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function(d) {
            let tip = ""
            if(d.children != undefined){
                tip = "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Companies</span>: </td>" +
                    "<td style='text-align: right;'>" + getNumberOfChildren(d) + "</td></tr>" +
                    "<tr><td style='text-align: center; padding-left: 5px; padding-right: 5px; color: dodgerblue;' colspan='2'>Click on the bar to expand</td></tr>"
            }
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                    "<td style='text-align: right;'>" + d.data.name + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                    "<td style='text-align: right;'>" + Math.round(d.value*100)/100 + "</td></tr>" +
                    tip +
                    "</table>")
                .style("top", (d3.event.pageY + 30)+"px")
                .style("left",(d3.event.pageX + 30)+"px")
        }
        let mouseleave = function(d) {
            chart.tooltip
                .style("opacity", 0)
        }

        bar.append("rect")
            .attr("x", this.x(0))
            .attr("width", d => this.x(d.value) - this.x(0))
            .attr("height", this.barStep * (1 - this.barPadding))
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
                bar.selectAll('#limit').remove()
                const pos_x = chart.x(actual.value)
                bar.append('line')
                    .attr('id', 'limit')
                    .attr('x1', pos_x)
                    .attr('y1', 0)
                    .attr('x2', pos_x)
                    .attr('y2', chart.barStep)
                    .attr('stroke', 'red')
                bar.append('text')
                    .attr('class', 'divergence')
                    .attr('x', (a) => chart.x(a.value))
                    .attr('y', (a) => chart.barStep * (1 - chart.barPadding) * 2 /3)
                    .attr('fill', 'white')
                    .attr('text-anchor', 'right')
                    .text((a, idx) => {
                        const divergence = ((a.value - actual.value)/actual.value * 100).toFixed(1)
                        let text = ''
                        if (divergence > 0) text += '+'
                        text += `${divergence}%`
                        return idx !== i ? text : '';
                    })
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                bar.selectAll('#limit').remove()
                bar.selectAll('.divergence').remove()
                mouseleave(actual);
            })
            .on('mousemove',mousemove);

        return g;
    }
}

function stagger(x, barStep) {
    let value = 0;
    return (d, i) => {
        const t = `translate(${x(value) - x(0)},${barStep * i})`;
        value += d.value;
        return t;
    };
}

function stack(i, x, barStep) {
    let value = 0;
    return d => {
        const t = `translate(${x(value) - x(0)},${barStep * i})`;
        value += d.value;
        return t;
    };
}


function getNumberOfChildren(n) {
    if (n.children == undefined) return 1;
    var nb_children = 0;
    n.children.forEach(function(c){
        nb_children += getNumberOfChildren(c);
    });
    return nb_children;
}





